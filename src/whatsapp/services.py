import logging
from datetime import datetime
from typing import Any

from sqlalchemy import or_

from src.database import SessionLocal, utcnow
from src.models.account import Account
from src.models.contact import Contact
from src.models.whatsapp_response import WhatsAppTemplateResponse
from src.whatsapp.cloud_api import meta_client
from src.whatsapp.repositories import WhatsAppRepository

logger = logging.getLogger("whatsapp.services")

# Mapping of Quick Reply button payloads and titles to Meta WhatsApp template language codes
LANGUAGE_PAYLOAD_MAP: dict[str, str] = {
    # Standard technical payloads
    "LANG_EN": "en",
    "LANG_HI": "hi",
    "LANG_KN": "kn",
    "LANG_TE": "te",
    "LANG_TA": "ta",
    "LANG_BN": "bn",
    "LANG_MR": "mr",
    "LANG_GU": "gu",
    # Exact button texts in English
    "ENGLISH": "en",
    "HINDI": "hi",
    "KANNADA": "kn",
    "TELUGU": "te",
    "TAMIL": "ta",
    "BENGALI": "bn",
    "MARATHI": "mr",
    "GUJARATI": "gu",
    # Exact native scripts as sent in payload/text from Meta Quick Replies
    "ಕನ್ನಡ": "kn",
    "हिंदी": "hi",
    "हिन्दी": "hi",
    "తెలుగు": "te",
    "தமிழ்": "ta",
    "বাংলা": "bn",
    "मराठी": "mr",
    "ગુજરાતી": "gu",
}
DEFAULT_LANGUAGE: str = "en"

# Mapping of exact button payloads and phrases
RESPONSE_INTENT_MAP: dict[str, str] = {
    # Interested payloads and variations
    "INTERESTED": "interested",
    "RESP_INTERESTED": "interested",
    "INTRESTED": "interested",
    "RESP_INTRESTED": "interested",
    "YES": "interested",
    "YES_INTERESTED": "interested",
    "YES_INTRESTED": "interested",
    "I AM INTERESTED": "interested",
    "I'M INTERESTED": "interested",
    "IM INTERESTED": "interested",
    "I INTERESTED": "interested",
    "I AM INTRESTED": "interested",
    "I'M INTRESTED": "interested",
    "IM INTRESTED": "interested",
    "I INTRESTED": "interested",
    "NEED 1 ON 1 DISCUSSION": "interested",
    "NEED 1 ON 1": "interested",
    "1 ON 1 DISCUSSION": "interested",
    "1 ON 1": "interested",
    "AM INTERESTED": "interested",
    "AM INTRESTED": "interested",
    "YES I AM INTERESTED": "interested",
    "YES I'M INTERESTED": "interested",
    "YES I AM INTRESTED": "interested",
    "PLEASE SHARE DETAILS": "interested",
    "SHARE DETAILS": "interested",
    "NEED DETAILS": "interested",
    "TELL ME MORE": "interested",
    "CALL ME": "interested",
    "ಆಸಕ್ತಿ ಇದೆ": "interested",  # Kannada: Interested
    "ಹೌದು": "interested",  # Kannada: Yes
    "ನನಗೆ ಆಸಕ್ತಿ ಇದೆ": "interested",  # Kannada: I am interested
    "ಮಾಹಿತಿ ನೀಡಿ": "interested",  # Kannada: Share info
    "रुचि है": "interested",  # Hindi: Interested
    "हाँ": "interested",  # Hindi: Yes
    "हाँ, रुचि है": "interested",
    "मुझे रुचि है": "interested",  # Hindi: I am interested
    "जानकारी चाहिए": "interested",  # Hindi: Need info
    # Not Interested payloads and variations
    "NOT_INTERESTED": "not_interested",
    "RESP_NOT_INTERESTED": "not_interested",
    "NOT_INTRESTED": "not_interested",
    "RESP_NOT_INTRESTED": "not_interested",
    "NO": "not_interested",
    "NO_NOT_INTERESTED": "not_interested",
    "NOT INTERESTED": "not_interested",
    "NOT INTRESTED": "not_interested",
    "I AM NOT INTERESTED": "not_interested",
    "I'M NOT INTERESTED": "not_interested",
    "IM NOT INTERESTED": "not_interested",
    "I AM NOT INTRESTED": "not_interested",
    "I'M NOT INTRESTED": "not_interested",
    "IM NOT INTRESTED": "not_interested",
    "DONT WANT": "not_interested",
    "DON'T WANT": "not_interested",
    "DO NOT WANT": "not_interested",
    "NO THANKS": "not_interested",
    "NO THANK YOU": "not_interested",
    "STOP": "not_interested",
    "UNSUBSCRIBE": "not_interested",
    "ಆಸಕ್ತಿ ಇಲ್ಲ": "not_interested",  # Kannada: Not Interested
    "ಇಲ್ಲ": "not_interested",  # Kannada: No
    "ನನಗೆ ಆಸಕ್ತಿ ಇಲ್ಲ": "not_interested",  # Kannada: I am not interested
    "ಬೇಡ": "not_interested",  # Kannada: Don't want
    "रुचि नहीं है": "not_interested",  # Hindi: Not Interested
    "नहीं": "not_interested",  # Hindi: No
    "मुझे रुचि नहीं है": "not_interested",  # Hindi: I am not interested
    "नहीं चाहिए": "not_interested",  # Hindi: Don't want
}


def classify_response_intent(raw_text: str | None) -> str | None:
    """
    Classifies a customer's button click or typed text into 'interested' or 'not_interested'.
    Supports:
    1. Exact button payloads (e.g. 'INTERESTED', 'RESP_INTERESTED', 'NEED 1 ON 1 DISCUSSION')
    2. Case-insensitive variations ('I am interested', 'i intrested', 'Need 1 on 1 discussion')
    3. Substring matching for common positive/negative intent phrases.
    """
    if not raw_text:
        return None

    cleaned = str(raw_text).strip()
    upper = cleaned.upper()

    # 1. Exact match in predefined map (check cleaned and uppercase)
    if cleaned in RESPONSE_INTENT_MAP:
        return RESPONSE_INTENT_MAP[cleaned]
    if upper in RESPONSE_INTENT_MAP:
        return RESPONSE_INTENT_MAP[upper]

    # 2. Check for negative intent first (to prevent 'not interested' or 'not intrested' matching 'interested')
    not_interested_keywords = [
        "NOT INTEREST",
        "NOT INTREST",
        "NO INTEREST",
        "NO INTREST",
        "DONT WANT",
        "DON'T WANT",
        "DO NOT WANT",
        "NO THANKS",
        "NO THANK",
        "NOT NOW",
        "ಆಸಕ್ತಿ ಇಲ್ಲ",
        "ಬೇಡ",
        "रुचि नहीं",
        "नहीं चाहिए",
    ]
    for kw in not_interested_keywords:
        if kw in upper or kw in cleaned:
            return "not_interested"

    # 3. Check for positive intent keywords ('interested', 'intrested', '1 on 1 discussion', etc.)
    interested_keywords = [
        "INTEREST",  # Matches "interested", "interesting", "I am interested"
        "INTREST",   # Matches "intrested", "intresting", "I am intrested"
        "1 ON 1",    # Matches "Need 1 on 1 discussion", "1 on 1", "1 on 1 call"
        "1-ON-1",
        "ONE ON ONE",
        "SHARE DETAILS",
        "SEND DETAILS",
        "NEED DETAILS",
        "MORE INFO",
        "CALL ME",
        "TELL ME",
        "ಆಸಕ್ತಿ ಇದೆ",
        "ಮಾಹಿತಿ",
        "रुचि है",
        "जानकारी",
    ]
    for kw in interested_keywords:
        if kw in upper or kw in cleaned:
            return "interested"

    return None


class WhatsAppService:
    def __init__(self, repository: WhatsAppRepository | None = None):
        self.repo = repository or WhatsAppRepository()

    def update_contact_language(
        self, contact_id: int | None, language_code: str
    ) -> None:
        """Persists customer's preferred language into PostgreSQL Contact custom_fields."""
        if not contact_id:
            return
        try:
            with SessionLocal() as db:
                contact = db.query(Contact).filter(Contact.id == contact_id).first()
                if contact:
                    custom_fields = dict(contact.custom_fields or {})
                    custom_fields["preferred_language"] = language_code
                    contact.custom_fields = custom_fields
                    db.commit()
                    logger.info(
                        f"Updated contact ID {contact_id} preferred_language to '{language_code}'"
                    )
        except Exception as e:
            logger.error(f"Error updating language for contact {contact_id}: {e}")

    def record_template_response(
        self,
        contact_id: int | None,
        customer_phone: str,
        template_name: str,
        response_status: str,
        button_text: str | None = None,
        button_payload: str | None = None,
        outbound_wamid: str | None = None,
        inbound_wamid: str | None = None,
        template_language: str | None = None,
    ) -> None:
        """
        Records customer response (interested/not_interested) in PostgreSQL:
        1. Normalizes phone to last 10 digits (stripping country code 91) to guarantee matching.
        2. Inserts a row in whatsapp_template_responses linked to Contact & Account.
        3. Updates Contact.custom_fields['template_responses'] with latest response per template.
        """
        try:
            # Normalize to 10 digits (remove leading 91 or +)
            raw_digits = "".join(filter(str.isdigit, str(customer_phone or "")))
            phone_10 = raw_digits[-10:] if len(raw_digits) >= 10 else raw_digits

            with SessionLocal() as db:
                account_id = None
                company_id = 1

                if contact_id:
                    contact = db.query(Contact).filter(Contact.id == contact_id).first()
                    if contact:
                        account_id = contact.account_id
                        company_id = contact.company_id or 1

                        # Update Contact.custom_fields with this template's status
                        custom_fields = dict(contact.custom_fields or {})
                        tmpl_responses = dict(
                            custom_fields.get("template_responses") or {}
                        )
                        tmpl_responses[template_name] = {
                            "status": response_status,
                            "button_text": button_text,
                            "responded_at": datetime.now().isoformat(),
                        }
                        custom_fields["template_responses"] = tmpl_responses
                        contact.custom_fields = custom_fields

                # If account_id was not on contact, look up directly in accounts_merged by last 10 digits
                matched_acc = None
                if not account_id and phone_10:
                    matched_acc = (
                        db.query(Account)
                        .filter(Account.phone.like(f"%{phone_10}"))
                        .first()
                    )
                    if matched_acc:
                        account_id = matched_acc.id
                        company_id = matched_acc.company_id or 1
                        # If contact exists, also link this contact to the account
                        if contact_id:
                            contact = (
                                db.query(Contact)
                                .filter(Contact.id == contact_id)
                                .first()
                            )
                            if contact and not contact.account_id:
                                contact.account_id = matched_acc.id

                # Synchronize Account.waba_interested status in PostgreSQL
                target_acc = matched_acc or (db.query(Account).filter(Account.id == account_id).first() if account_id else None)
                if target_acc:
                    if response_status == "interested":
                        target_acc.waba_interested = True
                    elif response_status == "not_interested":
                        target_acc.waba_interested = False

                # Insert granular record in whatsapp_template_responses using clean 10-digit phone
                new_resp = WhatsAppTemplateResponse(
                    company_id=company_id,
                    account_id=account_id,
                    contact_id=contact_id,
                    customer_phone=phone_10,
                    template_name=template_name,
                    template_language=template_language,
                    response_status=response_status,
                    button_text=button_text,
                    button_payload=button_payload,
                    outbound_wamid=outbound_wamid,
                    inbound_wamid=inbound_wamid,
                    extra_data={
                        "raw_button_payload": button_payload,
                        "raw_button_text": button_text,
                    },
                )
                db.add(new_resp)
                db.commit()

                print("\n" + "=" * 60)
                print(" [POSTGRESQL TEMPLATE RESPONSE SAVED]")
                print(f" Account ID:    {account_id}")
                print(f" Contact ID:    {contact_id}")
                print(f" Template:      {template_name}")
                print(f" Response:      {response_status.upper()} ('{button_text}')")
                print("=" * 60 + "\n", flush=True)

                logger.info(
                    f"Saved WhatsApp template response in PostgreSQL: account={account_id}, contact={contact_id}, template={template_name}, status={response_status}"
                )
        except Exception as e:
            logger.error(f"Failed to record template response in PostgreSQL: {e}")

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

                # Look up if an Account exists with this 10-digit phone number
                linked_account = (
                    db.query(Account).filter(Account.phone.like(f"%{phone_10}")).first()
                )
                account_id_to_link = linked_account.id if linked_account else None

                # Generate unique placeholder email because contacts_merged.email is NOT NULL
                placeholder_email = f"wa_{phone_10}@whatsapp.crm"

                new_contact = Contact(
                    account_id=account_id_to_link,
                    first_name=first_name,
                    last_name=last_name,
                    email=placeholder_email,
                    mobile=phone_10,
                    phone=phone_10,
                    lead_source="WhatsApp",
                    company_id=linked_account.company_id if linked_account else 1,
                    created_time=datetime.now(),
                    custom_fields={"created_via": "whatsapp_webhook"},
                )
                db.add(new_contact)
                db.commit()
                db.refresh(new_contact)

                logger.info(
                    f"Auto-created new Contact ID {new_contact.id} (Account ID: {account_id_to_link}) for 10-digit phone {phone_10}"
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
            quoted_msg = await self.repo.get_message_by_wamid(
                reply_to_info["message_id"]
            )
            if quoted_msg:
                q_content = quoted_msg.get("content", {})
                q_text = (
                    q_content.get("rendered", {}).get("body")
                    or q_content.get("text")
                    or quoted_msg.get("preview_text")
                    or f"Template: {q_content.get('template_name', '')}"
                )
                reply_to_info["quoted_text"] = q_text
                reply_to_info["quoted_from"] = quoted_msg.get(
                    "customer_wa_id"
                ) or quoted_msg.get("business_phone_number_id")

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

        # 5. Process Language Selection Flow (Quick Reply / Interactive Button Reply)
        content = event.get("content", {})
        button_payload = str(
            content.get("payload")
            or content.get("button_id")
            or content.get("text")
            or ""
        ).strip()

        # Check exact match or uppercase match
        selected_lang = LANGUAGE_PAYLOAD_MAP.get(
            button_payload
        ) or LANGUAGE_PAYLOAD_MAP.get(button_payload.upper())

        if selected_lang:
            print("\n" + "#" * 60)
            print(" [LANGUAGE SELECTION DETECTED]")
            print(f" Customer: {customer_wa_id}")
            print(f" Payload:  {button_payload}")
            print(f" Mapped:   {selected_lang}")
            print(
                f" Action:   Persisting and sending 'welcome_message' ({selected_lang})..."
            )
            print("#" * 60 + "\n", flush=True)

            logger.info(
                f"Customer {customer_wa_id} selected language '{selected_lang}' via payload '{button_payload}'"
            )
            # A. Persist preferred language in MongoDB conversation
            await self.repo.update_conversation_language(
                conversation_id=conversation["_id"],
                language_code=selected_lang,
            )

            # B. Persist preferred language in PostgreSQL contact custom_fields
            self.update_contact_language(contact_id, selected_lang)

            # C. Send localized welcome/acknowledgment template in selected language
            try:
                auto_reply = await self.send_template_message(
                    recipient_phone=customer_wa_id,
                    template_name="welcome_message",
                    language_code=selected_lang,
                    business_phone_number_id=business_phone_number_id,
                )
                saved_msg["auto_reply"] = auto_reply
            except Exception as e:
                logger.error(
                    f"Failed to auto-send localized template 'welcome_message' to {customer_wa_id}: {e}"
                )
                print(f" [ERROR AUTO-SENDING TEMPLATE] {e}", flush=True)

        # 6. Process Template Response Flow (Interested / Not Interested on any sent template)
        # Check payload, button text, or direct typed text
        raw_reply_text = (
            button_payload or content.get("text") or event.get("preview_text") or ""
        )
        response_intent = classify_response_intent(raw_reply_text)

        if response_intent:
            # Determine which template this button click is replying to
            target_template_name = None
            target_outbound_wamid = None
            target_template_lang = None

            # Check reply_to context (Meta's context.id links directly to the quoted template message)
            if reply_to_info and reply_to_info.get("message_id"):
                quoted_wamid = reply_to_info.get("message_id")
                quoted_doc = await self.repo.get_message_by_wamid(quoted_wamid)
                if quoted_doc and quoted_doc.get("type") == "template":
                    target_template_name = quoted_doc.get("content", {}).get(
                        "template_name"
                    )
                    target_template_lang = quoted_doc.get("content", {}).get("language")
                    target_outbound_wamid = quoted_wamid

            # If customer clicked a Quick Reply button without quoting context, look up the last template sent
            if not target_template_name:
                last_tmpl = await self.repo.db.messages.find_one(
                    {
                        "customer_wa_id": customer_wa_id,
                        "direction": "outbound",
                        "type": "template",
                    },
                    sort=[("timestamp", -1)],
                )
                if last_tmpl:
                    target_template_name = last_tmpl.get("content", {}).get(
                        "template_name"
                    )
                    target_template_lang = last_tmpl.get("content", {}).get("language")
                    target_outbound_wamid = last_tmpl.get("wamid")

            # Fallback if unknown
            target_template_name = target_template_name or "unknown_template"

            # Persist response in PostgreSQL whatsapp_template_responses & Contact.custom_fields
            self.record_template_response(
                contact_id=contact_id,
                customer_phone=customer_wa_id,
                template_name=target_template_name,
                response_status=response_intent,
                button_text=content.get("text"),
                button_payload=button_payload,
                outbound_wamid=target_outbound_wamid,
                inbound_wamid=event.get("wamid"),
                template_language=target_template_lang,
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
        print(" Status:    SENT_TO_META")
        print("=" * 60 + "\n", flush=True)

        return saved_msg

    async def send_template_message(
        self,
        recipient_phone: str,
        template_name: str,
        language_code: str | None = None,
        components: list[dict[str, Any]] | None = None,
        business_phone_number_id: str | None = None,
    ) -> dict:
        """Sends an approved template message and persists it, falling back to customer's preferred language."""
        clean_phone = "".join(filter(str.isdigit, str(recipient_phone)))
        phone_id = business_phone_number_id or meta_client.phone_number_id

        # 1. Resolve contact & conversation first to check saved language preferences
        contact_id, resolved_name = self.resolve_or_create_contact(clean_phone)
        conversation = await self.repo.get_or_create_conversation(
            customer_wa_id=clean_phone,
            business_phone_number_id=phone_id,
            contact_id=contact_id,
            customer_name=resolved_name,
        )

        # 2. Determine effective language: explicitly provided > conversation saved preference > default "en"
        effective_language = (
            language_code or conversation.get("preferred_language") or DEFAULT_LANGUAGE
        )

        # Sanitize components: only include non-empty parameter lists
        sanitized_components: list[dict[str, Any]] | None = None
        if components:
            valid_comps = [
                c
                for c in components
                if isinstance(c, dict)
                and c.get("parameters")
                and len(c.get("parameters")) > 0
            ]
            sanitized_components = valid_comps if valid_comps else None

        # 3. Send via Meta Cloud API
        meta_response = await meta_client.send_template_message(
            to_phone=clean_phone,
            template_name=template_name,
            language_code=effective_language,
            components=sanitized_components,
            phone_number_id=phone_id,
        )

        wamid = None
        messages_resp = meta_response.get("messages", [])
        if messages_resp and len(messages_resp) > 0:
            wamid = messages_resp[0].get("id")

        now = utcnow()

        # Look up saved template definition in DB to store rendered body text & buttons
        tmpl_def = await self.repo.get_template(
            waba_id=meta_client.phone_number_id or "",
            name=template_name,
            language=effective_language,
        )
        if not tmpl_def:
            # Try finding by name across WABA
            matching_tmpls = await self.repo.list_templates()
            tmpl_def = next(
                (t for t in matching_tmpls if t.get("name") == template_name), None
            )

        body_text = ""
        buttons_rendered: list[dict[str, Any]] = []
        if tmpl_def and tmpl_def.get("components"):
            for comp in tmpl_def["components"]:
                if comp.get("type") == "BODY":
                    body_text = comp.get("text", "")
                elif comp.get("type") == "BUTTONS":
                    for b in comp.get("buttons", []):
                        buttons_rendered.append(
                            {"id": b.get("text", ""), "title": b.get("text", "")}
                        )

        # Replace dynamic parameters (e.g. {{1}}, {{2}}) in rendered preview text if provided
        rendered_body = body_text or f"Template: {template_name}"
        if components:
            for c in components:
                if c.get("type") == "body" and c.get("parameters"):
                    for idx, param in enumerate(c.get("parameters", []), start=1):
                        val = param.get("text") or param.get(param.get("type"), "")
                        rendered_body = rendered_body.replace(
                            f"{{{{{idx}}}}}", str(val)
                        )

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
                "language": effective_language,
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
        print(f" Template:  {template_name} (Language: {effective_language})")
        print(f" WAMID:     {wamid}")
        print(" Status:    SENT_TO_META")
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
