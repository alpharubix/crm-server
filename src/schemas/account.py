from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, field_serializer
from typing import Optional, Dict, Any, Literal, List
from datetime import datetime
from src.schemas.user import UserResponse
from src.schemas.contact import ContactResponse

# Account Status Options
AccountStatusType = Literal[
    "Awareness",
    "Attention", 
    "Assessment",
    "Lender Review",
    "Not Interested",
    "Location Unserviceable"
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
    "No Requirement"
]

class AccountBase(BaseModel):
    id:str
    # Identity & Contact (Required)
    first_name: str
    last_name: str
    email: EmailStr
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
    
    # Location (Optional)
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    
    # Flags & Dates (Optional)
    waba_interested: Optional[bool] = False
    call_back_date_time: Optional[datetime] = None
    
    # Custom Fields (JSONB)
    custom_fields: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_by_id: str
    created_time: str|datetime
    modified_time: str|datetime

    @field_validator('created_time', mode='after')
    @classmethod
    def parse_created_time(cls, value):
        if isinstance(value, str):
            date = datetime.fromisoformat(value)
            return datetime.fromisoformat(value)
        raise ValueError('created_time must be in string format')

    @field_validator('modified_time', mode='after')
    @classmethod
    def parse_modified_time(cls, value):
        if isinstance(value, str):
            dt = datetime.fromisoformat(value)
            return dt
        raise ValueError("modified_time must be in string format")


    @field_validator('created_by_id', mode='after')
    @classmethod
    def parse_created_by(cls, value):
        if isinstance(value, str):
            return int(value)
        raise ValueError("id must be in string format")

    @field_validator('id', mode='after')
    @classmethod
    def parse_id(cls, value):
        if isinstance(value, str):
            return int(value)
        raise ValueError("id must be in string format")

class AccountResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    account_name: str|None
    email: EmailStr
    phone: str
    business_status: str|None
    distributor_code: str|None
    pincode: str|None
    call_back_date_time: datetime|None
    type_of_business: str|None
    industry: str|None
    account_status:Any
    city: str | None
    state: str | None
    pincode: str | None
    source: str | None
    account_stage:Any
    created_by_id: int
    created_time: datetime
    modified_time: datetime
    created_by: UserResponse|None
    owner: UserResponse|None
    account_linked_contact: List[ContactResponse] = []
    notes: Any
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("id")
    @classmethod
    def parse_id(cls, value):
        if isinstance(value, int):
         return str(value)
        else:
            return value
    @field_serializer("created_by_id")
    @classmethod
    def serialize_bigint(cls, value):
        if isinstance(value, int):
            return str(value)
        return value

class GetlistAccountResponse(BaseModel):
    data:List[AccountResponse]
    page_info:dict[str, Any]