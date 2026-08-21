from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import (
    BaseModel,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from src.schemas.contact import ContactResponse
from src.schemas.deals import IST, DealSchema
from src.schemas.user import UserResponseAccount

# Account Status Options
AccountStatusType = Literal[
    "Awareness",
    "Attention",
    "Assessment",
    "Lender Review",
    "Not Interested",
    "Location Unserviceable",
]

# Account Stage Options
AccountStageType = Literal[
    "Initial Pitch",
    "Product Offering",
    "Doc List Shared to Cust",
    "Partial Docs Rec",
    "Yet To Review",
    "Under Internal Review",
    "In Review with Lender",
    "Interested",
    "Commercial NI",
    "Location not doable",
    "No Requirement",
]


class AddressInfo(BaseModel):
    """Structured address info"""

    street: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    pincode: str | None = None
    years_residing: int | None = None
    gps_location: str | None = None
    ownership_type: str | None = None


class BusinessDetailsInfo(BaseModel):
    """Structured business details"""

    type_of_business: str | None = None
    industry: str | None = None
    vintage_years: int | None = None
    registration_type: str | None = None
    suppliers: str | None = None
    description: str | None = None
    gstn: str | None = None
    pan: str | None = None


class ReferencePerson(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    relationship: str | None = None
    address: str | None = None


class CustomerReferencesInfo(BaseModel):
    person1: ReferencePerson = Field(default_factory=ReferencePerson)
    person2: ReferencePerson = Field(default_factory=ReferencePerson)


# Employment type choices for Salaried profile
EmploymentType = Literal[
    "Private Employee",
    "Government Employee",
    "Retired",
    "Others",
]


class CustomerSalaryDetailsInfo(BaseModel):
    """Structured salary details — applicable when profile_type = 'Salaried'."""

    employment_type: EmploymentType | None = None  # select
    employer_name: str | None = None  # text
    employment_vintage: int | None = None  # number (years)
    annual_income: float | None = None  # number (currency)


class AccountBase(BaseModel):
    # Identity & Contact (Required)
    first_name: str
    last_name: str
    email: str | None = None
    phone: str = Field(..., min_length=10, max_length=15)
    account_name: str

    # Workflow & Assignment (Optional)
    account_owner_id: str | None = None
    account_status: Any
    account_stage: Any
    source: str | None = None
    business_status: str | None = None
    distributor_code: str | None = None

    # Business Details (Optional)
    type_of_business: str | None = None
    industry: str | None = None
    profile_type: str | None = None

    # Location (Optional)
    city: str | None = None
    state: str | None = None
    pincode: str | None = None

    # Flags & Dates (Optional)
    waba_interested: bool | None = False
    call_back_date_time: datetime | None = None
    created_time: datetime | None = Field(default_factory=lambda: datetime.now(IST))

    # Custom Fields (JSONB)
    custom_fields: dict[str, Any] | None = Field(default_factory=dict)

    # ========== NEW FIELDS (Add these) ==========
    # Account Status Section
    source_type: str | None = None  # Direct, Referral, Partner, Website, Other
    source_other: str | None = None
    mothers_name: str | None = None
    preferred_languages: list[str] | None = Field(default_factory=list)
    parent_account_id: str | None = None
    source_date: date | None = None
    source_description: str | None = None

    # New JSONB fields (will be handled in controller, but add to schema)
    business_details: dict[str, Any] | None = Field(default_factory=dict)
    business_premise_address: dict[str, Any] | None = Field(default_factory=dict)
    applicant_residence_address: dict[str, Any] | None = Field(default_factory=dict)
    co_applicant_residence_address: dict[str, Any] | None = Field(default_factory=dict)
    customer_references: dict[str, Any] | None = Field(default_factory=dict)

    # Customer Salary Details — optional; frontend enforces when profile_type = "Salaried"
    customer_salary_details: dict[str, Any] | None = Field(default_factory=dict)

    @field_validator("pincode", mode="before")
    @classmethod
    def validate_pincode(cls, value):
        if value is None or value == "":
            return value
        try:
            pincode = int(str(value).strip())
        except ValueError as exc:
            raise ValueError("pincode must be numeric") from exc

        pincode_str = str(pincode)
        if len(pincode_str) != 6:
            raise ValueError("pincode must be a 6 digit numeric value")
        return pincode_str


from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel


class AccountStatusJourneyItem(BaseModel):
    name: str
    duration: str
    color: str
    startDate: str
    endDate: str
    updatedBy: str


class AccountResponse(BaseModel):
    # Existing fields (keep all)
    id: str | None = None
    first_name: Any | None = None
    last_name: Any | None = None
    account_name: str | None = None
    email: str | None = None
    phone: str | None = None
    business_status: str | None = None
    distributor_code: str | None = None
    call_back_date_time: datetime | None = None
    type_of_business: str | None = None
    industry: str | None = None
    account_status: Any | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    source: str | None = None
    account_stage: Any | None = None
    profile_type: str | None = None
    is_priority_account: str | None = None
    created_by_id: str | None = None
    created_time: datetime | None = None
    modified_time: datetime | None = None
    modified_by_id: str | None = None
    assignment_date: datetime | None = None
    custom_fields: dict[str, Any] | None = Field(default_factory=dict)
    created_by: UserResponseAccount | None = None
    modified_by: UserResponseAccount | None = None
    account_owner_id: str | None = None
    owner: UserResponseAccount | None = None
    account_linked_contact: list["ContactResponse"] | None = None
    deals: list["DealSchema"] | None = None
    tickets: list[dict[str, Any]] | None = Field(default_factory=list)
    deal_documents: list[dict[str, Any]] | None = Field(default_factory=list)
    revenue: list[dict[str, Any]] | None = Field(default_factory=list)
    notes: Any | None = None

    # ========== NEW FIELDS (Add these) ==========
    source_type: str | None = None
    source_other: str | None = None
    mothers_name: str | None = None
    preferred_languages: list[str] | None = Field(default_factory=list)
    parent_account_id: str | None = None
    parent_account: Optional["AccountResponse"] = None  # For nested parent account
    source_date: date | None = None
    source_description: str | None = None

    # New JSONB fields
    business_details: dict[str, Any] | None = Field(default_factory=dict)
    business_premise_address: dict[str, Any] | None = Field(default_factory=dict)
    applicant_residence_address: dict[str, Any] | None = Field(default_factory=dict)
    co_applicant_residence_address: dict[str, Any] | None = Field(default_factory=dict)
    customer_references: dict[str, Any] | None = Field(default_factory=dict)

    # Customer Salary Details — optional; frontend enforces when profile_type = "Salaried"
    customer_salary_details: dict[str, Any] | None = Field(default_factory=dict)

    # Account Status Journey
    status_journey: list[AccountStatusJourneyItem] | None = Field(default_factory=list)
    journey: list[AccountStatusJourneyItem] | None = Field(default_factory=list)

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def extract_custom_attributes(cls, value):
        if (
            hasattr(value, "_tickets_list")
            or hasattr(value, "_deal_documents_list")
            or hasattr(value, "_revenue_list")
        ):
            data = {}
            if hasattr(value, "__table__"):
                for c in value.__table__.columns:
                    data[c.name] = getattr(value, c.name, None)

            for attr in (
                "owner",
                "created_by",
                "modified_by",
                "account_linked_contact",
                "deals",
                "notes",
                "business_details",
                "business_premise_address",
                "applicant_residence_address",
                "co_applicant_residence_address",
                "customer_references",
                "customer_salary_details",
                "custom_fields",
                "parent_account",
                "status_journey",
                "journey",
            ):
                if hasattr(value, attr):
                    data[attr] = getattr(value, attr)

            data["tickets"] = getattr(value, "_tickets_list", [])
            data["deal_documents"] = getattr(value, "_deal_documents_list", [])
            data["revenue"] = getattr(value, "_revenue_list", [])
            return data
        return value

    @field_serializer(
        "created_time", "modified_time", "call_back_date_time", "assignment_date"
    )
    def serialize_datetime(self, value):
        if value:
            dt = datetime.fromisoformat(str(value)).replace(tzinfo=UTC).astimezone(IST)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return value

    @field_validator(
        "id",
        "account_owner_id",
        "created_by_id",
        "modified_by_id",
        "parent_account_id",
        mode="before",
    )
    @classmethod
    def coerce_ids_to_str(cls, value):
        return str(value) if value is not None else None

    # ========== NEW HYBRID PROPERTIES (Backward compatible) ==========
    @property
    def current_business_type(self) -> str | None:
        """Returns from new JSONB if exists, else from old column"""
        if self.business_details and self.business_details.get("type_of_business"):
            return self.business_details["type_of_business"]
        return self.type_of_business

    @property
    def current_industry(self) -> str | None:
        if self.business_details and self.business_details.get("industry"):
            return self.business_details["industry"]
        return self.industry

    @property
    def current_city(self) -> str | None:
        if self.business_premise_address and self.business_premise_address.get("city"):
            return self.business_premise_address["city"]
        return self.city

    @property
    def current_state(self) -> str | None:
        if self.business_premise_address and self.business_premise_address.get("state"):
            return self.business_premise_address["state"]
        return self.state

    @property
    def current_pincode(self) -> str | None:
        if self.business_premise_address and self.business_premise_address.get(
            "pincode"
        ):
            return self.business_premise_address["pincode"]
        return self.pincode


# Add this for the parent relationship
AccountResponse.model_rebuild()


class GetlistAccountResponse(BaseModel):
    data: list[AccountResponse] = []
    page_info: dict[str, Any]


class GetAssociatedAccountResponse(BaseModel):
    id: str
    account_name: str | Any
    phone: str | Any = None
    email: str | None = None

    @field_serializer("id")
    @classmethod
    def parse_id(cls, value):
        if isinstance(value, int):
            return str(value)
        else:
            return value


class AccountItem(BaseModel):
    id: str
    account_name: Any

    @field_validator("id", mode="before")
    @classmethod
    def serialize_id(cls, value):
        return str(value)


class ListAccountsResponse(BaseModel):
    data: list[AccountItem]


class AccountStatusHistoryResponse(BaseModel):
    id: str
    account_id: str
    company_id: int | None = 1
    status: str
    name: str | None = None
    start_time: datetime
    start_time_formatted: str | None = None
    startDate: str | None = None
    end_time: datetime | None = None
    end_time_formatted: str | None = None
    endDate: str | None = None
    total_time_stayed: str | None = None
    duration_seconds: int | None = None
    duration: str | None = None
    is_current: bool = False
    moved_by_id: int
    moved_by_name: str | None = None
    updatedBy: str | None = None
    color: str | None = "blue"

    class Config:
        from_attributes = True




class AccountStatusJourneyResponse(BaseModel):
    id: str
    name: str
    owner: str
    currentStatus: str
    journey: list[AccountStatusJourneyItem]
