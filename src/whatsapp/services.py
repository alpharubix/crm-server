import logging
from datetime import datetime
from typing import Any

from sqlalchemy import or_

from src.database import SessionLocal, utcnow
from src.models.account import Account  # noqa: F401
from src.models.contact import Contact
from src.models.user import User  # noqa: F401
from src.whatsapp.cloud_api import meta_client
from src.whatsapp.repositories import WhatsAppRepository

logger = logging.getLogger("whatsapp.services")


class WhatsAppService:
    def __init__(self, repository: WhatsAppRepository | None = None):
        self.repo = repository or WhatsAppRepository()

    # -------------------------------------------------------------------------
    # Contact Resolution (PostgreSQL)
    # -------------------------------------------------------------------------

    def resolve_or_create_contact(
        self,
        phone_number: str,
        profile_name: str | None = None,
    ) -> tuple[int | None, str | None]:
        """
        Looks up a contact in PostgreSQL contacts_merged by the last 10 digits of the phone number.
        If not found, auto-creates a new Contact in PostgreSQL with the phone number & profile name.
        """
        clean_digits = "".join(filter(str.isdigit, str(phone_number or "")))
        if not clean_digits:
            return None, profile_name

        phone_10 = clean_digits[-10:] if len(clean_digits) >= 10 else clean_digits

        try:
            with SessionLocal() as db:
                existing_contact = (
                    db.query(Contact)
                    .filter(
                        or_(
                            Contact.mobile.like(f"%{phone_10}"),
                            Contact.phone.like(f"%{phone_10}"),
                        )
                    )
                    .first()
                )

                if existing_contact:
                    full_name = f"{existing_contact.first_name or ''} {existing_contact.last_name or ''}".strip()
                    return existing_contact.id, full_name or profile_name

                # Auto-create new Contact in PostgreSQL
                contact_name = (
                    profile_name.strip()
                    if profile_name and profile_name.strip()
                    else "WhatsApp Lead"
                )
                name_parts = contact_name.split(" ", 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else None

                # Generate unique placeholder email because contacts_merged.email is NOT NULL
                placeholder_email = f"wa_{clean_digits}@whatsapp.crm"

                new_contact = Contact(
                    first_name=first_name,
                    last_name=last_name,
                    email=placeholder_email,
                    mobile=clean_digits,
                    phone=clean_digits,
                    lead_source="WhatsApp",
                    company_id=1,
                    created_time=datetime.now(),
                    custom_fields={"created_via": "whatsapp_webhook"},
                )
                db.add(new_contact)
                db.commit()
                db.refresh(new_contact)

                logger.info(
                    f"Auto-created new Contact ID {new_contact.id} for phone {clean_digits}"
                )
                return new_contact.id, contact_name

        except Exception as e:
            logger.error(
                f"Error resolving or creating PostgreSQL contact for {phone_number}: {e}"
            )
            return None, profile_name

    # -------------------------------------------------------------------------
    # Inbound Event Processing
    # -------------------------------------------------------------------------

    async def process_inbound_message(self, event: dict[str, Any]) -> dict:
        """Processes an incoming customer message."""
        customer_wa_id = event["customer_wa_id"]
        business_phone_number_id = event["business_phone_number_id"]
        profile_name = event.get("customer_name")

        # 1. Resolve or auto-create CRM contact
        contact_id, resolved_name = self.resolve_or_create_contact(
            customer_wa_id, profile_name
        )

        # 2. Find or create conversation
        conversation = await self.repo.get_or_create_conversation(
            customer_wa_id=customer_wa_id,
            business_phone_number_id=business_phone_number_id,
            contact_id=contact_id,
            customer_name=resolved_name,
        )

        reply_to_info = event.get("reply_to")
        if reply_to_info and reply_to_info.get("message_id"):
            # Attempt to resolve the quoted message text for clean UI quote preview
            quoted_msg = await self.repo.get_message_by_wamid(reply_to_info["message_id"])
            if quoted_msg:
                q_content = quoted_msg.get("content", {})
                q_text = (
                    q_content.get("rendered", {}).get("body")
                    or q_content.get("text")
                    or quoted_msg.get("preview_text")
                    or f"Template: {q_content.get('template_name', '')}"
                )
                reply_to_info["quoted_text"] = q_text
                reply_to_info["quoted_from"] = quoted_msg.get("customer_wa_id") or quoted_msg.get("business_phone_number_id")

        # 3. Save message document
        msg_doc = {
            "conversation_id": conversation["_id"],
            "contact_id": contact_id,
            "business_phone_number_id": business_phone_number_id,
            "customer_wa_id": customer_wa_id,
            "wamid": event["wamid"],
            "direction": "inbound",
            "type": event["type"],
            "content": event["content"],
            "reply_to": reply_to_info,
            "status": "received",
            "status_history": [
                {
                    "status": "received",
                    "timestamp": event["timestamp"],
                }
            ],
            "timestamp": event["timestamp"],
            "raw_payload": event.get("raw_payload"),
        }
        saved_msg = await self.repo.save_message(msg_doc)

        # 4. Update conversation preview and increment unread count
        await self.repo.update_conversation_last_message(
            conversation_id=conversation["_id"],
            message_id=saved_msg["_id"],
            preview=event.get("preview_text", ""),
            direction="inbound",
            status="received",
            timestamp=event["timestamp"],
            increment_unread=True,
        )

        return saved_msg

    async def process_status_update(self, event: dict[str, Any]) -> dict | None:
        """Processes delivery and read receipt status updates from Meta."""
        wamid = event.get("wamid")
        new_status = event.get("status")
        timestamp = event.get("timestamp", utcnow())
        error_details = event.get("error")
        raw_payload = event.get("raw_payload")

        if not wamid or not new_status:
            return None

        updated_msg = await self.repo.update_message_status(
            wamid=wamid,
            new_status=new_status,
            status_timestamp=timestamp,
            error_details=error_details,
            raw_status_event=raw_payload,
        )

        if updated_msg:
            # If this message was the conversation's last message, update last_message_status
            conv_id = updated_msg.get("conversation_id")
            if conv_id:
                conv = await self.repo.get_conversation_by_id(conv_id)
                if conv and conv.get("last_message_id") == str(updated_msg["_id"]):
                    await self.repo.update_conversation_last_message(
                        conversation_id=conv_id,
                        message_id=updated_msg["_id"],
                        preview=conv.get("last_message_preview", ""),
                        direction=conv.get("last_message_direction", "outbound"),
                        status=new_status,
                        timestamp=conv.get("last_message_at") or timestamp,
                        increment_unread=False,
                    )

        return updated_msg

    # -------------------------------------------------------------------------
    # Outbound Message Sending
    # -------------------------------------------------------------------------

    async def send_text_message(
        self,
        recipient_phone: str,
        text: str,
        business_phone_number_id: str | None = None,
    ) -> dict:
        """Sends an outbound plain text message and persists it."""
        clean_phone = "".join(filter(str.isdigit, str(recipient_phone)))
        phone_id = business_phone_number_id or meta_client.phone_number_id

        # 1. Send via Meta Cloud API
        meta_response = await meta_client.send_text_message(
            to_phone=clean_phone,
            text=text,
            phone_number_id=phone_id,
        )

        wamid = None
        messages_resp = meta_response.get("messages", [])
        if messages_resp and len(messages_resp) > 0:
            wamid = messages_resp[0].get("id")

        now = utcnow()

        # 2. Resolve contact & conversation
        contact_id, resolved_name = self.resolve_or_create_contact(clean_phone)
        conversation = await self.repo.get_or_create_conversation(
            customer_wa_id=clean_phone,
            business_phone_number_id=phone_id,
            contact_id=contact_id,
            customer_name=resolved_name,
        )

        # 3. Persist outbound message document
        msg_doc = {
            "conversation_id": conversation["_id"],
            "contact_id": contact_id,
            "business_phone_number_id": phone_id,
            "customer_wa_id": clean_phone,
            "wamid": wamid,
            "direction": "outbound",
            "type": "text",
            "content": {"text": text},
            "status": "sent_to_meta",
            "status_history": [
                {
                    "status": "sent_to_meta",
                    "timestamp": now,
                }
            ],
            "timestamp": now,
            "raw_payload": meta_response,
        }
        saved_msg = await self.repo.save_message(msg_doc)

        # 4. Update conversation last message
        await self.repo.update_conversation_last_message(
            conversation_id=conversation["_id"],
            message_id=saved_msg["_id"],
            preview=text,
            direction="outbound",
            status="sent_to_meta",
            timestamp=now,
            increment_unread=False,
        )

        print("\n" + "=" * 60)
        print(" [WHATSAPP OUTBOUND TEXT MESSAGE SENT]")
        print(f" To:        {clean_phone} (Contact ID: {contact_id})")
        print(f" WAMID:     {wamid}")
        print(f" Content:   {text}")
        print(f" Status:    SENT_TO_META")
        print("=" * 60 + "\n", flush=True)

        return saved_msg

    async def send_template_message(
        self,
        recipient_phone: str,
        template_name: str,
        language_code: str = "en",
        components: list[dict[str, Any]] | None = None,
        business_phone_number_id: str | None = None,
    ) -> dict:
        """Sends an approved template message and persists it."""
        clean_phone = "".join(filter(str.isdigit, str(recipient_phone)))
        # Sanitize components: only include non-empty parameter lists
        sanitized_components: list[dict[str, Any]] | None = None
        if components:
            valid_comps = [
                c for c in components
                if isinstance(c, dict) and c.get("parameters") and len(c.get("parameters")) > 0
            ]
            sanitized_components = valid_comps if valid_comps else None

        phone_id = business_phone_number_id or meta_client.phone_number_id

        # 1. Send via Meta Cloud API
        meta_response = await meta_client.send_template_message(
            to_phone=clean_phone,
            template_name=template_name,
            language_code=language_code,
            components=sanitized_components,
            phone_number_id=phone_id,
        )

        wamid = None
        messages_resp = meta_response.get("messages", [])
        if messages_resp and len(messages_resp) > 0:
            wamid = messages_resp[0].get("id")

        now = utcnow()

        # 2. Resolve contact & conversation
        contact_id, resolved_name = self.resolve_or_create_contact(clean_phone)
        conversation = await self.repo.get_or_create_conversation(
            customer_wa_id=clean_phone,
            business_phone_number_id=phone_id,
            contact_id=contact_id,
            customer_name=resolved_name,
        )

        # Look up saved template definition in DB to store rendered body text & buttons
        tmpl_def = await self.repo.get_template(
            waba_id=meta_client.phone_number_id or "",
            name=template_name,
            language=language_code,
        )
        if not tmpl_def:
            # Try finding by name across WABA
            matching_tmpls = await self.repo.list_templates()
            tmpl_def = next((t for t in matching_tmpls if t.get("name") == template_name), None)

        body_text = ""
        buttons_rendered: list[dict[str, Any]] = []
        if tmpl_def and tmpl_def.get("components"):
            for comp in tmpl_def["components"]:
                if comp.get("type") == "BODY":
                    body_text = comp.get("text", "")
                elif comp.get("type") == "BUTTONS":
                    for b in comp.get("buttons", []):
                        buttons_rendered.append({"id": b.get("text", ""), "title": b.get("text", "")})

        # Replace dynamic parameters (e.g. {{1}}, {{2}}) in rendered preview text if provided
        rendered_body = body_text or f"Template: {template_name}"
        if components:
            for c in components:
                if c.get("type") == "body" and c.get("parameters"):
                    for idx, param in enumerate(c.get("parameters", []), start=1):
                        val = param.get("text") or param.get(param.get("type"), "")
                        rendered_body = rendered_body.replace(f"{{{{{idx}}}}}", str(val))

        # 3. Persist outbound message document
        msg_doc = {
            "conversation_id": conversation["_id"],
            "contact_id": contact_id,
            "business_phone_number_id": phone_id,
            "customer_wa_id": clean_phone,
            "wamid": wamid,
            "direction": "outbound",
            "type": "template",
            "content": {
                "template_name": template_name,
                "language": language_code,
                "components": components or [],
                "rendered": {
                    "body": rendered_body,
                    "buttons": buttons_rendered,
                },
            },
            "status": "sent_to_meta",
            "status_history": [
                {
                    "status": "sent_to_meta",
                    "timestamp": now,
                }
            ],
            "timestamp": now,
            "raw_payload": meta_response,
        }
        saved_msg = await self.repo.save_message(msg_doc)

        # 4. Update conversation last message
        preview = f"[Template: {template_name}]"
        await self.repo.update_conversation_last_message(
            conversation_id=conversation["_id"],
            message_id=saved_msg["_id"],
            preview=preview,
            direction="outbound",
            status="sent_to_meta",
            timestamp=now,
            increment_unread=False,
        )

        print("\n" + "=" * 60)
        print(" [WHATSAPP OUTBOUND TEMPLATE MESSAGE SENT]")
        print(f" To:        {clean_phone} (Contact ID: {contact_id})")
        print(f" Template:  {template_name} (Language: {language_code})")
        print(f" WAMID:     {wamid}")
        print(f" Status:    SENT_TO_META")
        print("=" * 60 + "\n", flush=True)

        return saved_msg

    # -------------------------------------------------------------------------
    # Template Synchronization
    # -------------------------------------------------------------------------

    async def sync_templates_from_meta(self, waba_id: str | None = None) -> list[dict]:
        """Fetches approved templates from Meta and upserts into templates collection."""
        raw_templates = await meta_client.fetch_waba_templates(waba_id=waba_id)
        effective_waba = waba_id or meta_client.phone_number_id

        synced_docs = []
        for t in raw_templates:
            doc = {
                "waba_id": effective_waba,
                "name": t.get("name"),
                "language": t.get("language"),
                "category": t.get("category", "UTILITY"),
                "status": t.get("status", "UNKNOWN"),
                "components": t.get("components", []),
            }
            res = await self.repo.upsert_template(doc)
            synced_docs.append(res)

        return synced_docs


whatsapp_service = WhatsAppService()
