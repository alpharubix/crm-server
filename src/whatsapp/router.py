import logging

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import PlainTextResponse

from src.whatsapp.schemas import (
    SendTemplateMessageRequest,
    SendTextMessageRequest,
)
from src.whatsapp.services import whatsapp_service
from src.whatsapp.webhook import (
    parse_meta_webhook,
    verify_signature,
    verify_webhook_token,
)

logger = logging.getLogger("whatsapp.router")

# Router for Meta Webhook endpoints (at /webhooks/whatsapp)
webhook_router = APIRouter(prefix="/webhooks/whatsapp", tags=["whatsapp-webhooks"])

# Router for CRM WhatsApp Inbox APIs (at /api/v1/whatsapp)
inbox_router = APIRouter(prefix="/api/v1/whatsapp", tags=["whatsapp-inbox"])


# =========================================================================
# 1. META WEBHOOK ENDPOINTS
# =========================================================================


@webhook_router.get("", response_class=PlainTextResponse)
@webhook_router.get("/", response_class=PlainTextResponse)
async def webhook_verification(request: Request):
    """
    Handles Meta's GET verification handshake.
    Query parameters: hub.mode, hub.verify_token, hub.challenge.
    """
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    challenge_response = verify_webhook_token(mode, token, challenge)
    print("\n" + "=" * 60)
    print(" [WHATSAPP WEBHOOK GET VERIFICATION]")
    print(f" Hub Mode:      {mode}")
    print(f" Verify Token:  {token}")
    print(f" Challenge:     {challenge}")
    print(" Result:        VERIFIED & CHALLENGE RETURNED (HTTP 200)")
    print("=" * 60 + "\n", flush=True)
    return challenge_response


@webhook_router.post("")
@webhook_router.post("/")
async def webhook_receive_event(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
):
    """
    Receives incoming webhook events from Meta (messages, status updates, button clicks).
    Verifies HMAC signature, normalizes payloads, and persists documents idempotently.
    """
    raw_body = await request.body()

    # 1. Signature Verification
    if not verify_signature(raw_body, x_hub_signature_256):
        logger.warning("Rejected webhook due to invalid X-Hub-Signature-256")
        print("\n [WHATSAPP WEBHOOK] Rejected: Invalid signature header\n", flush=True)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid signature",
        )

    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Malformed webhook JSON: {e}")
        return {"status": "ignored", "error": "malformed_json"}

    # 2. Parse & Normalize incoming messages and status events
    incoming_messages, status_updates = parse_meta_webhook(payload)

    print("\n" + "=" * 60)
    print(" [WHATSAPP WEBHOOK POST EVENT RECEIVED]")

    # 3. Process Inbound Customer Messages
    for msg_event in incoming_messages:
        print(" -> INCOMING MESSAGE:")
        print(
            f"    From:     {msg_event.get('customer_wa_id')} (Name: {msg_event.get('customer_name') or 'Unknown'})"
        )
        print(f"    Type:     {msg_event.get('type')}")
        print(f"    Content:  {msg_event.get('content')}")
        print(f"    WAMID:    {msg_event.get('wamid')}")
        try:
            saved = await whatsapp_service.process_inbound_message(msg_event)
            print(
                f"    Saved:    PostgreSQL Contact ID: {saved.get('contact_id')} | MongoDB Message ID: {saved.get('_id')}"
            )
        except Exception as e:
            print(f"    Error:    Failed to process inbound message: {e}")
            logger.error(
                f"Failed to process inbound message wamid={msg_event.get('wamid')}: {e}"
            )

    # 4. Process Status Updates (sent, delivered, read, failed)
    for st_event in status_updates:
        print(" -> OUTBOUND STATUS UPDATE:")
        print(f"    WAMID:     {st_event.get('wamid')}")
        print(f"    Status:    {st_event.get('status', '').upper()}")
        print(f"    Recipient: {st_event.get('recipient_id')}")
        if st_event.get("error"):
            print(f"    Error:     {st_event.get('error')}")
        try:
            await whatsapp_service.process_status_update(st_event)
        except Exception as e:
            print(f"    Error:     Failed to update status: {e}")
            logger.error(
                f"Failed to process status update wamid={st_event.get('wamid')}: {e}"
            )

    print("=" * 60 + "\n", flush=True)
    return {"status": "success"}


# =========================================================================
# 2. CRM INBOX & MESSAGING REST APIS
# =========================================================================


@inbox_router.get("/conversations")
async def list_conversations(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    unread_only: bool = Query(default=False),
):
    """List customer conversations with pagination, unread filter, and search."""
    conversations, total = await whatsapp_service.repo.list_conversations(
        page=page, limit=limit, search=search, unread_only=unread_only
    )
    return {
        "status": "success",
        "data": conversations,
        "page_info": {
            "page": page,
            "limit": limit,
            "total_count": total,
        },
    }


@inbox_router.get("/conversations/{conversation_id}")
async def get_conversation_detail(conversation_id: str):
    """Get single conversation details."""
    conv = await whatsapp_service.repo.get_conversation_by_id(conversation_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return {"status": "success", "data": conv}


@inbox_router.get("/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    before_timestamp: str | None = Query(default=None),
    before_id: str | None = Query(default=None),
):
    """
    Fetch chronological messages for a conversation timeline with cursor pagination.
    """
    ts = None
    if before_timestamp:
        try:
            from datetime import datetime

            ts = datetime.fromisoformat(before_timestamp)
        except Exception:
            pass

    messages = await whatsapp_service.repo.get_conversation_messages(
        conversation_id=conversation_id,
        limit=limit,
        before_timestamp=ts,
        before_id=before_id,
    )
    return {"status": "success", "data": messages}


@inbox_router.post("/conversations/{conversation_id}/read")
async def mark_conversation_as_read(conversation_id: str):
    """Mark a conversation as read locally and reset unread count."""
    await whatsapp_service.repo.mark_conversation_read(conversation_id)
    return {"status": "success", "message": "Conversation marked as read"}


@inbox_router.post("/messages/text")
async def send_text_message(body: SendTextMessageRequest):
    """Send an outbound plain text message to a customer."""
    try:
        saved_msg = await whatsapp_service.send_text_message(
            recipient_phone=body.recipient_phone,
            text=body.text,
            business_phone_number_id=body.business_phone_number_id,
        )
        return {"status": "success", "data": saved_msg}
    except Exception as e:
        logger.error(f"Failed to send text message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@inbox_router.post("/messages/template")
async def send_template_message(body: SendTemplateMessageRequest):
    """Send an approved WhatsApp template to a customer."""
    try:
        saved_msg = await whatsapp_service.send_template_message(
            recipient_phone=body.recipient_phone,
            template_name=body.template_name,
            language_code=body.language_code,
            components=body.components,
            business_phone_number_id=body.business_phone_number_id,
        )
        return {"status": "success", "data": saved_msg}
    except Exception as e:
        logger.error(f"Failed to send template message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@inbox_router.get("/templates")
async def list_templates():
    """List synced WhatsApp templates."""
    templates = await whatsapp_service.repo.list_templates()
    return {"status": "success", "data": templates}


@inbox_router.post("/templates/sync")
async def sync_templates(waba_id: str | None = Query(default=None)):
    """Fetch and synchronize message templates from Meta WABA."""
    try:
        synced = await whatsapp_service.sync_templates_from_meta(waba_id=waba_id)
        return {"status": "success", "synced_count": len(synced), "data": synced}
    except Exception as e:
        logger.error(f"Template sync failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
