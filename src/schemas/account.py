from datetime import date, datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union

import pydantic
from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
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

    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None
    years_residing: Optional[int] = None
    gps_location: Optional[str] = None
    ownership_type: Optional[str] = None


class BusinessDetailsInfo(BaseModel):
    """Structured business details"""

    type_of_business: Optional[str] = None
    industry: Optional[str] = None
    vintage_years: Optional[int] = None
    registration_type: Optional[str] = None
    suppliers: Optional[str] = None
    description: Optional[str] = None
    gstn: Optional[str] = None
    pan: Optional[str] = None


class ReferencePerson(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    relationship: Optional[str] = None
    address: Optional[str] = None


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

    employment_type: Optional[EmploymentType] = None  # select
    employer_name: Optional[str] = None               # text
    employment_vintage: Optional[int] = None           # number (years)
    annual_income: Optional[float] = None              # number (currency)


class AccountBase(BaseModel):
    # Identity & Contact (Required)
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: str = Field(..., min_length=10, max_length=15)
    account_name: str

    # Workflow & Assignment (Optional)
    account_owner_id: Optional[str] = None
    account_status: Any
    account_stage: Any
    source: Optional[str] = None
    business_status: Optional[str] = None
    distributor_code: Optional[str] = None

    # Business Details (Optional)
    type_of_business: Optional[str] = None
    industry: Optional[str] = None
    profile_type: Optional[str] = None

    # Location (Optional)
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None

    # Flags & Dates (Optional)
    waba_interested: Optional[bool] = False
    call_back_date_time: Optional[datetime] = None
    created_time: Optional[datetime] = Field(default_factory=lambda: datetime.now(IST))

    # Custom Fields (JSONB)
    custom_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)

    # ========== NEW FIELDS (Add these) ==========
    # Account Status Section
    source_type: Optional[str] = None  # Direct, Referral, Partner, Website, Other
    source_other: Optional[str] = None
    mothers_name: Optional[str] = None
    preferred_languages: Optional[List[str]] = Field(default_factory=list)
    parent_account_id: Optional[str] = None
    source_date: Optional[date] = None
    source_description: Optional[str] = None

    # New JSONB fields (will be handled in controller, but add to schema)
    business_details: Optional[Dict[str, Any]] = Field(default_factory=dict)
    business_premise_address: Optional[Dict[str, Any]] = Field(default_factory=dict)
    applicant_residence_address: Optional[Dict[str, Any]] = Field(default_factory=dict)
    co_applicant_residence_address: Optional[Dict[str, Any]] = Field(
        default_factory=dict
    )
    customer_references: Optional[Dict[str, Any]] = Field(default_factory=dict)

    # Customer Salary Details — optional; frontend enforces when profile_type = "Salaried"
    customer_salary_details: Optional[Dict[str, Any]] = Field(default_factory=dict)

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


from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AccountResponse(BaseModel):
    # Existing fields (keep all)
    id: Optional[str] = None
    first_name: Optional[Any] = None
    last_name: Optional[Any] = None
    account_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    business_status: Optional[str] = None
    distributor_code: Optional[str] = None
    call_back_date_time: Optional[datetime] = None
    type_of_business: Optional[str] = None
    industry: Optional[str] = None
    account_status: Optional[Any] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    source: Optional[str] = None
    account_stage: Optional[Any] = None
    profile_type: Optional[str] = None
    is_priority_account: Optional[str] = None
    created_by_id: Optional[str] = None
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None
    modified_by_id: Optional[str] = None
    assignment_date: Optional[datetime | None] = None
    custom_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_by: Optional[UserResponseAccount] = None
    modified_by: Optional[UserResponseAccount] = None
    account_owner_id: Optional[str] = None
    owner: Optional[UserResponseAccount] = None
    account_linked_contact: Optional[List["ContactResponse"]] = None
    deals: Optional[List["DealSchema"]] = None
    tickets: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    deal_documents: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    revenue: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    notes: Optional[Any] = None

    # ========== NEW FIELDS (Add these) ==========
    source_type: Optional[str] = None
    source_other: Optional[str] = None
    mothers_name: Optional[str] = None
    preferred_languages: Optional[List[str]] = Field(default_factory=list)
    parent_account_id: Optional[str] = None
    parent_account: Optional["AccountResponse"] = None  # For nested parent account
    source_date: Optional[date] = None
    source_description: Optional[str] = None

    # New JSONB fields
    business_details: Optional[Dict[str, Any]] = Field(default_factory=dict)
    business_premise_address: Optional[Dict[str, Any]] = Field(default_factory=dict)
    applicant_residence_address: Optional[Dict[str, Any]] = Field(default_factory=dict)
    co_applicant_residence_address: Optional[Dict[str, Any]] = Field(
        default_factory=dict
    )
    customer_references: Optional[Dict[str, Any]] = Field(default_factory=dict)

    # Customer Salary Details — optional; frontend enforces when profile_type = "Salaried"
    customer_salary_details: Optional[Dict[str, Any]] = Field(default_factory=dict)

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def extract_custom_attributes(cls, value):
        if hasattr(value, "_tickets_list") or hasattr(value, "_deal_documents_list") or hasattr(value, "_revenue_list"):
            data = {}
            if hasattr(value, "__table__"):
                for c in value.__table__.columns:
                    data[c.name] = getattr(value, c.name, None)

            for attr in (
                "owner", "created_by", "modified_by", "account_linked_contact",
                "deals", "notes", "business_details", "business_premise_address",
                "applicant_residence_address", "co_applicant_residence_address",
                "customer_references", "customer_salary_details", "custom_fields",
                "parent_account"
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
            dt = (
                datetime.fromisoformat(str(value))
                .replace(tzinfo=timezone.utc)
                .astimezone(IST)
            )
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            return value

    @field_validator(
        "id", "account_owner_id", "created_by_id", "modified_by_id","parent_account_id", mode="before"
    )
    @classmethod
    def coerce_ids_to_str(cls, value):
        return str(value) if value is not None else None

    # ========== NEW HYBRID PROPERTIES (Backward compatible) ==========
    @property
    def current_business_type(self) -> Optional[str]:
        """Returns from new JSONB if exists, else from old column"""
        if self.business_details and self.business_details.get("type_of_business"):
            return self.business_details["type_of_business"]
        return self.type_of_business

    @property
    def current_industry(self) -> Optional[str]:
        if self.business_details and self.business_details.get("industry"):
            return self.business_details["industry"]
        return self.industry

    @property
    def current_city(self) -> Optional[str]:
        if self.business_premise_address and self.business_premise_address.get("city"):
            return self.business_premise_address["city"]
        return self.city

    @property
    def current_state(self) -> Optional[str]:
        if self.business_premise_address and self.business_premise_address.get("state"):
            return self.business_premise_address["state"]
        return self.state

    @property
    def current_pincode(self) -> Optional[str]:
        if self.business_premise_address and self.business_premise_address.get(
            "pincode"
        ):
            return self.business_premise_address["pincode"]
        return self.pincode


# Add this for the parent relationship
AccountResponse.model_rebuild()


class GetlistAccountResponse(BaseModel):
    data: List[AccountResponse] = []
    page_info: dict[str, Any]


class GetAssociatedAccountResponse(BaseModel):
    id: str
    account_name: str | Any
    phone: str | Any = None
    email: Optional[str] = None

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
    data: List[AccountItem]


class AccountStatusHistoryResponse(BaseModel):
    id: str
    account_id: str
    old_status: Optional[str]  # Optional because first status has no old_status
    new_status: str
    changed_by: int
    changed_at: datetime

    class Config:
        from_attributes = True  # this tells Pydantic: read from SQLAlchemy object
        # without this, it only reads plain dicts
