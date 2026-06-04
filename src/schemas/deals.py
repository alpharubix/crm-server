from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, List, Optional

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
    partner_code: str | None = None

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

    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Owner
    deal_owner_id: str | None = None
    crm_deal_id: str | None = None
    owner: UserResponseAccount | None = None  # optional now — safe for both paths
    notes: Any | None = None

    tickets: list[dict] | None = None
    revenue:list[dict] | None = None

    @model_validator(mode="before")
    @classmethod
    def extract_tickets_list(cls, value):
        if hasattr(value, "_tickets_list"):
            data = {
                c.name: getattr(value, c.name, None) for c in value.__table__.columns
            }
            data["tickets"] = value._tickets_list
            for attr in ("owner", "notes"):
                if hasattr(value, attr):
                    data[attr] = getattr(value, attr)
            return data
        return value

    @field_serializer("deal_call_back_datetime", "created_at", "updated_at")
    def serialize_datetime(self, value):
        if value:
            dt = (
                datetime.fromisoformat(str(value))
                .replace(tzinfo=timezone.utc)
                .astimezone(IST)
            )
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
    id: Optional[int] = None
    # Relationship
    account_id: str

    # Deal & Ticket Info
    ticket_id: Optional[int] = None
    ticket_number: Optional[int] = None
    deal_type: Optional[str] = None
    loan_type: Optional[str] = None
    type_of_login: Optional[str] = None
    type_of_case_login: Optional[str] = None
    ticket_login: Optional[str] = None
    deal_stage: Optional[str] = None
    deal_status: Optional[str] = None

    deal_expected_closing: Optional[date] = None
    deal_status_closing: Optional[date] = None
    lender_login_type: Optional[str] = None

    partner_code: Optional[str] = None
    # Amounts
    disbursed_amount: Optional[Decimal] = None
    sanction_amount: Optional[Decimal] = None
    approved_amount: Optional[Decimal] = None
    amount_required: Optional[Decimal] = None
    processing_fees: Optional[Decimal] = None
    mm_charges: Optional[Decimal] = None
    insurance_amount: Optional[Decimal] = None
    pf_percentage: Optional[Decimal] = None
    rate_of_interest: Optional[Decimal] = None
    interest_type: Optional[str] = None

    # Dates
    deal_call_back_datetime: Optional[datetime] = None
    disbursement_date: Optional[date] = None
    lender_login_date: Optional[date] = None
    loan_start_date: Optional[date] = None
    loan_end_date: Optional[date] = None
    targeted_disbursement_date: Optional[date] = None
    tenure: Optional[int] = None

    # Lender / Rejection
    lender_code: Optional[str] = None
    lender_name: Optional[str] = None
    customer_rejection_reason: Optional[str] = None
    customer_rejection_status_explanation: Optional[str] = None
    lender_rejection_reason: Optional[str] = None
    lender_rejection_status_explanation: Optional[str] = None

    # Attachments
    payment_receipt: Optional[Any] = None
    sanction_letter: Optional[str] = None
    potential: Optional[str] = None
    product: Optional[str] = None

    # Audit
    assignee_id: Optional[int] = None
    created_by: Optional[int] = None
    modified_by: Optional[int] = None

    # Account
    account_name: str

    # Timestamps
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(IST))
    updated_at: Optional[datetime] = None
    deal_owner_id: Optional[int] = None
    crm_deal_id: Optional[int] = None

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
    def serialize_datetime(self, value) -> Optional[str]:
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
