import logging

from fastapi import (
    APIRouter,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.responses import PlainTextResponse

from src.whatsapp.cloud_api import meta_client
from src.whatsapp.schemas import (
    BroadcastCampaignRequest,
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


import json
from datetime import datetime

from bson import ObjectId


def json_default_serializer(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")


# Real-Time WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict):
        try:
            payload_str = json.dumps(data, default=json_default_serializer)
        except Exception as e:
            logger.error(f"Failed to serialize WebSocket broadcast payload: {e}")
            return

        for connection in list(self.active_connections):
            try:
                await connection.send_text(payload_str)
            except Exception as e:
                logger.warning(f"Error sending to WS client, disconnecting: {e}")
                self.disconnect(connection)


ws_manager = ConnectionManager()

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
            # Broadcast to frontend clients in real time
            await ws_manager.broadcast(
                {
                    "type": "new_message",
                    "message": saved,
                    "conversation_id": str(saved.get("conversation_id")),
                }
            )
            # If an automatic localized welcome message was dispatched, broadcast it too
            if saved.get("auto_reply"):
                await ws_manager.broadcast(
                    {
                        "type": "new_message",
                        "message": saved["auto_reply"],
                        "conversation_id": str(saved.get("conversation_id")),
                    }
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
            updated_msg = await whatsapp_service.process_status_update(st_event)
            if updated_msg:
                # Broadcast updated status checkmark to frontend
                await ws_manager.broadcast(
                    {
                        "type": "status_update",
                        "wamid": st_event.get("wamid"),
                        "status": st_event.get("status"),
                        "conversation_id": str(updated_msg.get("conversation_id")),
                    }
                )
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


@inbox_router.get("/messages/by-phone")
async def get_messages_by_phone(
    phone: str = Query(..., description="Customer phone number"),
    limit: int = Query(default=6, ge=1, le=100),
    skip: int = Query(default=0, ge=0),
    direction: str | None = Query(default=None),
):
    """
    Fetch broadcast/chat messages from MongoDB messages collection matching customer_wa_id.
    Supports incremental 'See More' pagination.
    """
    messages, total = await whatsapp_service.repo.get_messages_by_phone(
        phone=phone,
        limit=limit,
        skip=skip,
        direction=direction,
    )
    has_more = (skip + len(messages)) < total
    return {
        "status": "success",
        "phone": phone,
        "total": total,
        "skip": skip,
        "limit": limit,
        "has_more": has_more,
        "data": messages,
    }


@inbox_router.post("/conversations/{conversation_id}/read")
async def mark_conversation_as_read(conversation_id: str):
    """Mark a conversation as read locally and reset unread count."""
    await whatsapp_service.repo.mark_conversation_read(conversation_id)
    # Broadcast read event to all connected UI clients in real time
    await ws_manager.broadcast(
        {
            "type": "conversation_read",
            "conversation_id": str(conversation_id),
        }
    )
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
        # Broadcast immediately to frontend clients via WebSocket
        await ws_manager.broadcast(
            {
                "type": "new_message",
                "message": saved_msg,
                "conversation_id": str(saved_msg.get("conversation_id")),
            }
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
        # Broadcast immediately to frontend clients via WebSocket
        await ws_manager.broadcast(
            {
                "type": "new_message",
                "message": saved_msg,
                "conversation_id": str(saved_msg.get("conversation_id")),
            }
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


@inbox_router.post("/broadcasts/send")
async def send_broadcast_campaign(body: BroadcastCampaignRequest):
    """
    Executes a bulk WhatsApp campaign to a list of recipients (from Excel/CSV).
    Throttles sends to respect Meta rate limits and updates CRM contacts & chat history.
    """
    import asyncio

    total = len(body.recipients)
    sent_count = 0
    failed_count = 0
    results: list[dict] = []

    for r in body.recipients:
        phone = "".join(filter(str.isdigit, str(r.phone)))
        if not phone or len(phone) < 10:
            failed_count += 1
            results.append({"phone": r.phone, "status": "failed", "error": "Invalid phone number"})
            continue

        try:
            if body.send_mode == "text" and r.custom_text:
                saved_msg = await whatsapp_service.send_text_message(
                    recipient_phone=phone,
                    text=r.custom_text,
                    business_phone_number_id=body.business_phone_number_id,
                )
            else:
                target_lang = r.language_code or body.language_code
                saved_msg = await whatsapp_service.send_template_message(
                    recipient_phone=phone,
                    template_name=body.template_name or "",
                    language_code=target_lang,
                    components=r.components,
                    business_phone_number_id=body.business_phone_number_id,
                )

            sent_count += 1
            results.append({"phone": phone, "status": "sent", "wamid": saved_msg.get("wamid")})

            # Broadcast new message to UI in real time
            await ws_manager.broadcast(
                {
                    "type": "new_message",
                    "message": saved_msg,
                    "conversation_id": str(saved_msg.get("conversation_id")),
                }
            )
        except Exception as e:
            failed_count += 1
            err_str = str(e)
            print(f"[BROADCAST SEND ERROR] Phone: {phone} | Error: {err_str}", flush=True)
            logger.error(f"[BROADCAST ERROR] Phone: {phone} | Error: {err_str}")
            results.append({"phone": phone, "status": "failed", "error": err_str})

        # Meta throttling: sleep 60ms between outbound sends to avoid 429
        await asyncio.sleep(0.06)

    overall_status = "success" if failed_count == 0 else ("failed" if sent_count == 0 else "partial")

    return {
        "status": overall_status,
        "campaign_name": body.campaign_name,
        "total": total,
        "sent": sent_count,
        "failed": failed_count,
        "details": results,
    }


@inbox_router.get("/accounts/{account_id}/responses")
async def get_account_template_responses(account_id: int):
    """
    Fetch all WhatsApp template responses (Interested / Not Interested) for an Account in PostgreSQL.
    Displays responses per template and per contact linked to this account.
    """
    from src.database import SessionLocal
    from src.models.account import Account
    from src.models.contact import Contact
    from src.models.whatsapp_response import WhatsAppTemplateResponse

    with SessionLocal() as db:
        account = db.query(Account).filter(Account.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Normalize account phone to last 10 digits
        acc_digits = "".join(filter(str.isdigit, str(account.phone or "")))
        acc_phone_10 = acc_digits[-10:] if len(acc_digits) >= 10 else acc_digits

        # Find responses linked by account_id OR by the account's 10-digit phone
        query = db.query(WhatsAppTemplateResponse)
        if acc_phone_10:
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    WhatsAppTemplateResponse.account_id == account_id,
                    WhatsAppTemplateResponse.customer_phone == acc_phone_10,
                    WhatsAppTemplateResponse.customer_phone.like(f"%{acc_phone_10}"),
                )
            )
        else:
            query = query.filter(WhatsAppTemplateResponse.account_id == account_id)

        responses = query.order_by(WhatsAppTemplateResponse.responded_at.desc()).all()

        # Build template-wise summary
        templates_summary: dict[str, dict] = {}
        items = []

        for r in responses:
            item = {
                "id": r.id,
                "template_name": r.template_name,
                "template_language": r.template_language,
                "response_status": r.response_status,
                "button_text": r.button_text,
                "customer_phone": r.customer_phone,
                "contact_id": r.contact_id,
                "responded_at": r.responded_at.isoformat() if r.responded_at else None,
            }
            items.append(item)

            # Aggregate per template name (takes the latest status for each template)
            if r.template_name not in templates_summary:
                templates_summary[r.template_name] = {
                    "template_name": r.template_name,
                    "latest_status": r.response_status,
                    "button_text": r.button_text,
                    "customer_phone": r.customer_phone,
                    "responded_at": r.responded_at.isoformat() if r.responded_at else None,
                    "response_count": 1,
                }
            else:
                templates_summary[r.template_name]["response_count"] += 1

        total_interested = sum(
            1 for t in templates_summary.values() if t["latest_status"] == "interested"
        )
        total_not_interested = sum(
            1 for t in templates_summary.values() if t["latest_status"] == "not_interested"
        )

        return {
            "status": "success",
            "account_id": account_id,
            "account_name": account.account_name or f"{account.first_name or ''} {account.last_name or ''}".strip(),
            "summary": {
                "total_unique_templates_responded": len(templates_summary),
                "total_interested": total_interested,
                "total_not_interested": total_not_interested,
                "templates": list(templates_summary.values()),
            },
            "history": items,
        }


@inbox_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for live WhatsApp updates (inbound messages, status ticks, mark read).
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            # Listen for client frames (keep-alive, mark_read, etc.)
            raw_text = await websocket.receive_text()
            if raw_text:
                try:
                    payload = json.loads(raw_text)
                    # Handle mark_read over WebSocket
                    if payload.get("action") == "mark_read" and payload.get("conversation_id"):
                        conv_id = str(payload["conversation_id"])
                        await whatsapp_service.repo.mark_conversation_read(conv_id)
                        # Broadcast confirmation to other tabs/clients
                        await ws_manager.broadcast({
                            "type": "conversation_read",
                            "conversation_id": conv_id,
                        })
                except Exception as parse_err:
                    logger.debug(f"Non-JSON or ignored WS message from client: {parse_err}")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


@inbox_router.get("/media/{media_id}")
async def get_media_proxy(media_id: str):
    """
    Secure media proxy to stream customer images, audio, video, documents
    to the frontend without exposing Meta access tokens to the browser.
    """
    try:
        meta_info = await meta_client.get_media_url(media_id)
        download_url = meta_info.get("url")
        if not download_url:
            raise HTTPException(status_code=404, detail="Media URL not found")

        content_bytes, content_type = await meta_client.download_media(download_url)
        return Response(content=content_bytes, media_type=content_type)
    except Exception as e:
        logger.error(f"Failed to proxy media {media_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
