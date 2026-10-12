import logging
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger("whatsapp.cloud_api")


class MetaWhatsAppClient:
    def __init__(
        self,
        access_token: str | None = None,
        phone_number_id: str | None = None,
        graph_version: str | None = None,
    ):
        self.access_token = access_token or settings.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = phone_number_id or settings.WHATSAPP_PHONE_NUMBER_ID
        self.graph_version = graph_version or settings.META_GRAPH_VERSION or "v26.0"
        self.base_url = f"https://graph.facebook.com/{self.graph_version}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def send_text_message(
        self,
        to_phone: str,
        text: str,
        preview_url: bool = False,
    ) -> dict[str, Any]:
        """
        Send a plain text message via Meta Cloud API.
        to_phone must be in international format without '+' (e.g. 919364111650).
        """
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "text",
            "text": {
                "preview_url": preview_url,
                "body": text,
            },
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            data = resp.json()

            if resp.status_code >= 400:
                logger.error(
                    f"Meta send_text error: status={resp.status_code}, data={data}"
                )
                raise RuntimeError(
                    f"Meta Cloud API error ({resp.status_code}): {data.get('error', {}).get('message', 'Unknown error')}"
                )

            return data

    async def send_template_message(
        self,
        to_phone: str,
        template_name: str,
        language_code: str = "en",
        components: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """
        Send an approved WhatsApp template.
        """
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_phone,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
            },
        }
        if components:
            payload["template"]["components"] = components

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            data = resp.json()

            if resp.status_code >= 400:
                logger.error(
                    f"Meta send_template error: status={resp.status_code}, data={data}"
                )
                raise RuntimeError(
                    f"Meta Cloud API error ({resp.status_code}): {data.get('error', {}).get('message', 'Unknown error')}"
                )

            return data

    async def mark_message_as_read(self, message_id: str) -> bool:
        """Inform Meta that an incoming message has been read by the business."""
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=self._headers())
                return resp.status_code == 200
        except Exception as e:
            logger.warning(f"Failed to mark message {message_id} as read on Meta: {e}")
            return False

    async def fetch_waba_templates(
        self, waba_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Fetch all message templates from the WhatsApp Business Account."""
        account_id = waba_id or settings.WHATSAPP_BUSINESS_ACCOUNT_ID
        if not account_id:
            raise ValueError("WHATSAPP_BUSINESS_ACCOUNT_ID is not configured")

        url = f"{self.base_url}/{account_id}/message_templates?limit=100"
        templates = []

        async with httpx.AsyncClient(timeout=20.0) as client:
            while url:
                resp = await client.get(url, headers=self._headers())
                if resp.status_code >= 400:
                    data = resp.json()
                    raise RuntimeError(
                        f"Failed to fetch templates: {data.get('error', {}).get('message', 'Unknown error')}"
                    )

                body = resp.json()
                templates.extend(body.get("data", []))
                url = body.get("paging", {}).get("next")

        return templates


meta_client = MetaWhatsAppClient()
