from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from src.schemas.user import UserResponseAccount

IST = timezone(timedelta(hours=5, minutes=30))


class DealSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Primary Key
    id: str | None = None
    # Relationship
    account_id: str | None = None

    # Deal & Ticket Info
    ticket_id: str | None = None
    ticket_number: str | None = None
    deal_type: str | None = None
    loan_type: str | None = None
    type_of_login: str | None = None
    type_of_case_login: str | None = None
    ticket_login: str | None = None
    deal_stage: str | None = None
    deal_status: str | None = None
    deal_approval: str | None = None
    deal_description: str | None = None
    type_of_loan: str | None = None

    # Amounts
    disbursed_amount: Decimal | None = None
    sanction_amount: Decimal | None = None
    approved_amount: Decimal | None = None
    amount_required: Decimal | None = None
    processing_fees: Decimal | None = None
    mm_charges: Decimal | None = None
    insurance_amount: Decimal | None = None
    pf_percentage: Decimal | None = None
    rate_of_interest: Decimal | None = None
    interest_type: str | None = None

    lender_login_type: str | None = None
    partner_name: str | None = None

    # Dates
    deal_call_back_datetime: datetime | None = None
    disbursement_date: date | None = None
    lender_login_date: date | None = None
    loan_start_date: date | None = None
    loan_end_date: date | None = None
    targeted_disbursement_date: date | None = None
    tenure: int | None = None

    # Lender / Rejection
    lender_code: str | None = None
    lender_name: str | None = None
    customer_rejection_reason: str | None = None
    customer_rejection_status_explanation: str | None = None
    lender_rejection_reason: str | None = None
    lender_rejection_status_explanation: str | None = None

    # Attachments
    payment_receipt: Any | None = None
    sanction_letter: str | None = None
    potential: str | None = None
    product: str | None = None

    # Audit
    assignee_id: str | None = None
    created_by: str | None = None
    modified_by: str | None = None

    deal_expected_closing: date | None = None
    deal_status_closing: date | None = None

    # Account
    account_name: str | None = None
    deal_name: str | None = None  # Auto-generated on creation

    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None
    modified_time: datetime | None = None
    created_time: datetime | None = None

    # Owner
    deal_owner_id: str | None = None
    crm_deal_id: str | None = None
    owner: UserResponseAccount | None = None  # optional now — safe for both paths
    notes: Any | None = None

    tickets: list[dict] | None = None
    revenue: list[dict] | None = None

    @model_validator(mode="before")
    @classmethod
    def extract_tickets_list(cls, value):
        if hasattr(value, "_tickets_list"):
            data = {
                c.name: getattr(value, c.name, None) for c in value.__table__.columns
            }
            data["tickets"] = value._tickets_list
            data["modified_time"] = getattr(
                value, "updated_at", getattr(value, "modified_time", None)
            )
            data["created_time"] = getattr(
                value, "created_at", getattr(value, "created_time", None)
            )
            data["type_of_loan"] = getattr(value, "loan_type", None)
            data["deal_approval"] = getattr(value, "deal_approval", None)
            data["deal_description"] = getattr(value, "deal_description", None)
            for attr in ("owner", "notes"):
                if hasattr(value, attr):
                    data[attr] = getattr(value, attr)
            return data
        elif isinstance(value, dict):
            if "type_of_loan" not in value or not value.get("type_of_loan"):
                value["type_of_loan"] = value.get("loan_type")
            if "loan_type" not in value or not value.get("loan_type"):
                value["loan_type"] = value.get("type_of_loan")
            if "deal_approval" not in value or not value.get("deal_approval"):
                value["deal_approval"] = value.get("deal_approval")
            if "deal_description" not in value:
                value["deal_description"] = value.get("deal_description")
        return value

    @field_serializer(
        "deal_call_back_datetime",
        "created_at",
        "updated_at",
        "modified_time",
        "created_time",
    )
    def serialize_datetime(self, value):
        if value:
            dt = datetime.fromisoformat(str(value)).replace(tzinfo=UTC).astimezone(IST)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return None

    @field_validator(
        "id",
        "account_id",
        "ticket_id",
        "ticket_number",
        "assignee_id",
        "created_by",
        "modified_by",
        "deal_owner_id",
        "crm_deal_id",
        mode="before",
    )
    @classmethod
    def coerce_ids_to_str(cls, value):
        return str(value) if value is not None else None


class DealListResponse(BaseModel):
    data: list[DealSchema] | dict | None = []
    page_info: dict[str, Any] | None = None


class DealCreationBody(BaseModel):
    # Primary Key
    id: int | None = None
    # Relationship
    account_id: str

    # Deal & Ticket Info
    ticket_id: int | None = None
    ticket_number: int | None = None
    deal_type: str | None = None
    loan_type: str | None = None
    type_of_login: str | None = None
    type_of_case_login: str | None = None
    ticket_login: str | None = None
    deal_stage: str | None = None
    deal_status: str | None = None
    deal_approval: str | None = None
    deal_description: str | None = None
    type_of_loan: str | None = None

    deal_expected_closing: date | None = None
    deal_status_closing: date | None = None
    lender_login_type: str | None = None

    partner_name: str | None = None
    # Amounts
    disbursed_amount: Decimal | None = None
    sanction_amount: Decimal | None = None
    approved_amount: Decimal | None = None
    amount_required: Decimal | None = None
    processing_fees: Decimal | None = None
    mm_charges: Decimal | None = None
    insurance_amount: Decimal | None = None
    pf_percentage: Decimal | None = None
    rate_of_interest: Decimal | None = None
    interest_type: str | None = None

    # Dates
    deal_call_back_datetime: datetime | None = None
    disbursement_date: date | None = None
    lender_login_date: date | None = None
    loan_start_date: date | None = None
    loan_end_date: date | None = None
    targeted_disbursement_date: date | None = None
    tenure: int | None = None

    # Lender / Rejection
    lender_code: str | None = None
    lender_name: str | None = None
    customer_rejection_reason: str | None = None
    customer_rejection_status_explanation: str | None = None
    lender_rejection_reason: str | None = None
    lender_rejection_status_explanation: str | None = None

    # Attachments
    payment_receipt: Any | None = None
    sanction_letter: str | None = None
    potential: str | None = None
    product: str | None = None

    # Audit
    assignee_id: int | None = None
    created_by: int | None = None
    modified_by: int | None = None

    # Account
    account_name: str
    deal_name: str | None = None  # Read-only, auto-generated by server

    # Timestamps
    created_at: datetime | None = Field(default_factory=lambda: datetime.now(IST))
    updated_at: datetime | None = None
    deal_owner_id: int | None = None
    crm_deal_id: int | None = None

    model_config = {"from_attributes": True}

    # ---- ID Validators ----
    @field_validator(
        "id",
        "ticket_id",
        "ticket_number",
        "assignee_id",
        "created_by",
        "modified_by",
        "deal_owner_id",
        "crm_deal_id",
        mode="before",  # ← before, not after
    )
    @classmethod
    def parse_ids(cls, value):
        return int(value) if value is not None else None

    # ---- Datetime Serializer ----
    @field_serializer("deal_call_back_datetime")
    def serialize_datetime(self, value) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=IST)
            return value.astimezone(IST).strftime("%Y-%m-%dT%H:%M:%S")
        if isinstance(value, str):
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=IST)
            return parsed.astimezone(IST).strftime("%Y-%m-%dT%H:%M:%S")
        return None
