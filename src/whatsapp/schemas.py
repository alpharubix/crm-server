from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

# -------------------------------------------------------------------------
# 1. MongoDB Document Schemas (Internal Representation)
# -------------------------------------------------------------------------


class ConversationDocument(BaseModel):
    id: str | None = Field(default=None, alias="_id")
    contact_id: int | None = Field(
        default=None,
        description="Links to PostgreSQL contacts_merged.id. None if customer is unknown/unlinked.",
    )
    business_phone_number_id: str = Field(
        ...,
        description="Meta Business Phone Number ID used for this channel.",
    )
    customer_wa_id: str = Field(
        ...,
        description="Customer WhatsApp phone number in canonical format (e.g. 919364111650).",
    )
    customer_name: str | None = Field(
        default=None,
        description="Customer profile or CRM name.",
    )
    status: Literal["open", "closed", "archived"] = "open"
    assigned_to: int | None = Field(
        default=None,
        description="CRM user ID assigned to this conversation.",
    )
    unread_count: int = 0
    last_message_id: str | None = None
    last_message_preview: str | None = None
    last_message_direction: Literal["inbound", "outbound"] | None = None
    last_message_status: str | None = None
    last_message_at: datetime | None = None
    preferred_language: str | None = Field(
        default=None,
        description="Customer's preferred WhatsApp template language code (e.g. 'en', 'hi', 'kn').",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class StatusHistoryEntry(BaseModel):
    status: str
    timestamp: datetime
    error: dict[str, Any] | None = None


class MessageDocument(BaseModel):
    id: str | None = Field(default=None, alias="_id")
    conversation_id: str = Field(
        ...,
        description="String representation of conversations ObjectId.",
    )
    contact_id: int | None = Field(
        default=None,
        description="Links to PostgreSQL contacts_merged.id. None if unlinked.",
    )
    business_phone_number_id: str
    customer_wa_id: str
    wamid: str | None = Field(
        default=None,
        description="Unique Meta WhatsApp Message ID (e.g. wamid.HBgLMOTE5...).",
    )
    direction: Literal["inbound", "outbound"]
    type: Literal[
        "text",
        "template",
        "interactive_reply",
        "image",
        "document",
        "audio",
        "video",
        "sticker",
        "location",
        "contacts",
        "unknown",
    ]
    content: dict[str, Any]
    status: Literal[
        "pending",
        "sent_to_meta",
        "sent",
        "delivered",
        "read",
        "failed",
        "received",
    ] = "pending"
    status_updated_at: datetime = Field(default_factory=datetime.utcnow)
    status_history: list[StatusHistoryEntry] = Field(default_factory=list)
    error: dict[str, Any] | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    raw_payload: dict[str, Any] | None = None


class TemplateDocument(BaseModel):
    id: str | None = Field(default=None, alias="_id")
    waba_id: str
    name: str
    language: str
    category: str
    status: str
    components: list[dict[str, Any]]
    synced_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# -------------------------------------------------------------------------
# 2. API Request / Response Schemas
# -------------------------------------------------------------------------


class SendTextMessageRequest(BaseModel):
    recipient_phone: str = Field(
        ...,
        description="Phone number in international format or 10-digit Indian mobile.",
    )
    text: str = Field(..., min_length=1)
    business_phone_number_id: str | None = None


class TemplateComponentParameter(BaseModel):
    type: Literal["text", "currency", "date_time", "image", "document", "video"]
    text: str | None = None
    image: dict[str, Any] | None = None
    document: dict[str, Any] | None = None
    video: dict[str, Any] | None = None


class TemplateComponentPayload(BaseModel):
    type: Literal["header", "body", "button"]
    sub_type: str | None = None
    index: str | None = None
    parameters: list[dict[str, Any]] = Field(default_factory=list)


class SendTemplateMessageRequest(BaseModel):
    recipient_phone: str
    template_name: str
    language_code: str | None = None
    components: list[dict[str, Any]] = Field(default_factory=list)
    business_phone_number_id: str | None = None


class BroadcastRecipient(BaseModel):
    phone: str
    custom_text: str | None = None
    language_code: str | None = None
    components: list[dict[str, Any]] = Field(default_factory=list)


class BroadcastCampaignRequest(BaseModel):
    campaign_name: str
    send_mode: Literal["template", "text"] = "template"
    template_name: str | None = None
    language_code: str | None = None
    recipients: list[BroadcastRecipient]
    business_phone_number_id: str | None = None
