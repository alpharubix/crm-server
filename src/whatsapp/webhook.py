import hashlib
import hmac
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status

from src.config import settings

logger = logging.getLogger("whatsapp.webhook")


def verify_webhook_token(
    mode: str | None, token: str | None, challenge: str | None
) -> str:
    """Verify Meta's GET verification handshake."""
    if not mode or not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing hub.mode or hub.verify_token",
        )

    expected_token = settings.WEBHOOK_VERIFY_TOKEN
    if mode == "subscribe" and (not expected_token or token == expected_token):
        return challenge or ""

    logger.warning("Webhook verification failed: token mismatch")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Verification token mismatch",
    )


def verify_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """
    Verify Meta's HMAC SHA-256 signature in X-Hub-Signature-256 header.
    Returns True if valid. If META_APP_SECRET is not configured, logs warning and allows in dev.
    """
    secret = settings.META_APP_SECRET
    if not secret:
        # In early testing or local dev without app secret
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        logger.warning("Missing or malformed X-Hub-Signature-256 header")
        return False

    expected_sig = signature_header[7:]
    computed_sig = hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed_sig, expected_sig)


def parse_meta_webhook(
    payload: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Parses a Meta WhatsApp webhook payload into two separate lists:
    1. Incoming customer messages
    2. Outbound status updates (sent, delivered, read, failed)
    """
    incoming_messages = []
    status_updates = []

    entries = payload.get("entry", [])
    for entry in entries:
        changes = entry.get("changes", [])
        for change in changes:
            field = change.get("field")
            if field != "messages":
                continue

            value = change.get("value", {})
            metadata = value.get("metadata", {})
            business_phone_number_id = metadata.get("phone_number_id", "")

            # Map contact wa_id -> profile name if available
            contacts_map = {}
            for c in value.get("contacts", []):
                wa_id = c.get("wa_id")
                name = c.get("profile", {}).get("name")
                if wa_id:
                    contacts_map[wa_id] = name

            # 1. Parse Inbound Messages
            raw_messages = value.get("messages", [])
            for msg in raw_messages:
                wamid = msg.get("id")
                from_wa_id = msg.get("from")
                msg_type = msg.get("type", "unknown")
                timestamp_str = msg.get("timestamp")

                dt = (
                    datetime.fromtimestamp(int(timestamp_str), tz=UTC)
                    if timestamp_str
                    else datetime.now(UTC)
                )
                customer_name = contacts_map.get(from_wa_id)

                content: dict[str, Any] = {}
                preview_text = ""

                if msg_type == "text":
                    body = msg.get("text", {}).get("body", "")
                    content = {"text": body}
                    preview_text = body

                elif msg_type == "interactive":
                    interactive = msg.get("interactive", {})
                    itype = interactive.get("type")
                    if itype == "button_reply":
                        btn_reply = interactive.get("button_reply", {})
                        content = {
                            "interaction_type": "button_reply",
                            "button_id": btn_reply.get("id"),
                            "text": btn_reply.get("title"),
                        }
                        preview_text = btn_reply.get("title", "Button response")
                    elif itype == "list_reply":
                        list_reply = interactive.get("list_reply", {})
                        content = {
                            "interaction_type": "list_reply",
                            "item_id": list_reply.get("id"),
                            "title": list_reply.get("title"),
                            "description": list_reply.get("description"),
                        }
                        preview_text = list_reply.get("title", "List response")
                    else:
                        content = interactive
                        preview_text = f"Interactive: {itype}"
                    msg_type = "interactive_reply"

                elif msg_type == "button":
                    btn = msg.get("button", {})
                    content = {
                        "interaction_type": "quick_reply",
                        "payload": btn.get("payload"),
                        "text": btn.get("text"),
                    }
                    preview_text = btn.get("text", "Button reply")
                    msg_type = "interactive_reply"

                elif msg_type in ("image", "document", "audio", "video", "sticker"):
                    media_obj = msg.get(msg_type, {})
                    content = {
                        "media_id": media_obj.get("id"),
                        "mime_type": media_obj.get("mime_type"),
                        "sha256": media_obj.get("sha256"),
                        "caption": media_obj.get("caption"),
                        "filename": media_obj.get("filename"),
                    }
                    preview_text = (
                        f"[{msg_type.upper()}] {media_obj.get('caption') or ''}".strip()
                    )

                else:
                    content = msg.get(msg_type, {})
                    preview_text = f"[{msg_type}]"

                incoming_messages.append(
                    {
                        "wamid": wamid,
                        "customer_wa_id": from_wa_id,
                        "customer_name": customer_name,
                        "business_phone_number_id": business_phone_number_id,
                        "direction": "inbound",
                        "type": msg_type,
                        "content": content,
                        "preview_text": preview_text,
                        "status": "received",
                        "timestamp": dt,
                        "raw_payload": msg,
                    }
                )

            # 2. Parse Outbound Status Events
            raw_statuses = value.get("statuses", [])
            for st in raw_statuses:
                wamid = st.get("id")
                recipient_id = st.get("recipient_id")
                status_val = st.get("status")  # sent, delivered, read, failed
                timestamp_str = st.get("timestamp")
                dt = (
                    datetime.fromtimestamp(int(timestamp_str), tz=UTC)
                    if timestamp_str
                    else datetime.now(UTC)
                )

                errors = st.get("errors")
                error_obj = errors[0] if errors and len(errors) > 0 else None

                status_updates.append(
                    {
                        "wamid": wamid,
                        "recipient_id": recipient_id,
                        "business_phone_number_id": business_phone_number_id,
                        "status": status_val,
                        "timestamp": dt,
                        "error": error_obj,
                        "raw_payload": st,
                    }
                )

    return incoming_messages, status_updates
