import hashlib
import hmac
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from main import app
from src.config import settings
from src.whatsapp.repositories import WhatsAppRepository
from src.whatsapp.webhook import parse_meta_webhook, verify_signature


@pytest.fixture
def test_client():
    return TestClient(app)


def generate_meta_signature(payload_bytes: bytes, secret: str) -> str:
    digest = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"sha256={digest}"


def test_webhook_get_verification(test_client):
    settings.WEBHOOK_VERIFY_TOKEN = "my_test_verify_token"

    # Valid verification handshake
    resp = test_client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "my_test_verify_token",
            "hub.challenge": "1158201444",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "1158201444"

    # Invalid token handshake
    bad_resp = test_client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "1158201444",
        },
    )
    assert bad_resp.status_code == 403


def test_webhook_signature_verification():
    secret = "test_meta_app_secret"
    settings.META_APP_SECRET = secret

    payload = b'{"object": "whatsapp_business_account"}'
    valid_sig = generate_meta_signature(payload, secret)
    invalid_sig = "sha256=invalidhexsignature123456789"

    assert verify_signature(payload, valid_sig) is True
    assert verify_signature(payload, invalid_sig) is False


def test_parse_meta_webhook_text_and_status():
    webhook_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "3549182178574893",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "919364111650",
                                "phone_number_id": "1328819806985211",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Aarav Patel"},
                                    "wa_id": "919876543210",
                                }
                            ],
                            "messages": [
                                {
                                    "from": "919876543210",
                                    "id": "wamid.TEST_INBOUND_001",
                                    "timestamp": "1760250000",
                                    "text": {"body": "Interested in business loans"},
                                    "type": "text",
                                }
                            ],
                            "statuses": [
                                {
                                    "id": "wamid.TEST_OUTBOUND_001",
                                    "status": "delivered",
                                    "timestamp": "1760250010",
                                    "recipient_id": "919876543210",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    inbound, statuses = parse_meta_webhook(webhook_payload)
    assert len(inbound) == 1
    assert inbound[0]["wamid"] == "wamid.TEST_INBOUND_001"
    assert inbound[0]["customer_wa_id"] == "919876543210"
    assert inbound[0]["customer_name"] == "Aarav Patel"
    assert inbound[0]["type"] == "text"
    assert inbound[0]["content"]["text"] == "Interested in business loans"

    assert len(statuses) == 1
    assert statuses[0]["wamid"] == "wamid.TEST_OUTBOUND_001"
    assert statuses[0]["status"] == "delivered"


def test_parse_meta_webhook_interactive_button():
    interactive_payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "3549182178574893",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "phone_number_id": "1328819806985211",
                            },
                            "contacts": [
                                {"profile": {"name": "Pooja"}, "wa_id": "919876543211"}
                            ],
                            "messages": [
                                {
                                    "from": "919876543211",
                                    "id": "wamid.TEST_BUTTON_001",
                                    "timestamp": "1760250020",
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {
                                            "id": "btn_hindi",
                                            "title": "Hindi",
                                        },
                                    },
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    inbound, _ = parse_meta_webhook(interactive_payload)
    assert len(inbound) == 1
    assert inbound[0]["type"] == "interactive_reply"
    assert inbound[0]["content"]["interaction_type"] == "button_reply"
    assert inbound[0]["content"]["button_id"] == "btn_hindi"
    assert inbound[0]["content"]["text"] == "Hindi"


@pytest.mark.asyncio
async def test_repository_out_of_order_status_protection():
    repo = WhatsAppRepository()
    now = datetime.now(UTC)

    # 1. Create a dummy message with status "delivered"
    test_wamid = "wamid.OUT_OF_ORDER_TEST"
    msg_data = {
        "conversation_id": "670a2f1b4c3e8a1234567890",
        "wamid": test_wamid,
        "direction": "outbound",
        "type": "text",
        "content": {"text": "Hello"},
        "status": "delivered",
        "status_history": [{"status": "delivered", "timestamp": now}],
        "timestamp": now,
    }
    await repo.save_message(msg_data)

    # 2. Update to "read"
    updated_read = await repo.update_message_status(
        wamid=test_wamid,
        new_status="read",
        status_timestamp=now,
    )
    assert updated_read["status"] == "read"

    # 3. An out-of-order delayed "sent" or "delivered" arrives:
    # Must NOT downgrade status back from "read" to "delivered"
    downgrade_attempt = await repo.update_message_status(
        wamid=test_wamid,
        new_status="delivered",
        status_timestamp=now,
    )
    assert downgrade_attempt["status"] == "read"
    # But it must be appended to status_history
    assert len(downgrade_attempt["status_history"]) >= 2

    # Clean up test message
    await repo.db.messages.delete_one({"wamid": test_wamid})


def test_response_intent_mappings():
    from src.whatsapp.services import RESPONSE_INTENT_MAP
    assert RESPONSE_INTENT_MAP.get("INTERESTED") == "interested"
    assert RESPONSE_INTENT_MAP.get("RESP_INTERESTED") == "interested"
    assert RESPONSE_INTENT_MAP.get("YES") == "interested"
    assert RESPONSE_INTENT_MAP.get("ಆಸಕ್ತಿ ಇದೆ") == "interested"
    assert RESPONSE_INTENT_MAP.get("रुचि है") == "interested"

    assert RESPONSE_INTENT_MAP.get("NOT_INTERESTED") == "not_interested"
    assert RESPONSE_INTENT_MAP.get("RESP_NOT_INTERESTED") == "not_interested"
    assert RESPONSE_INTENT_MAP.get("NO") == "not_interested"
    assert RESPONSE_INTENT_MAP.get("ಆಸಕ್ತಿ ಇಲ್ಲ") == "not_interested"
    assert RESPONSE_INTENT_MAP.get("रुचि नहीं है") == "not_interested"

