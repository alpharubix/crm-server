# from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
# from typing import Optional, Any
# from datetime import datetime
# from decimal import Decimal
# import re

# # --- SHARED PROPERTIES ---
# # Fields that can exist in both Input (Create) and Output (Read)
# class AccountBase(BaseModel):
#     # Critical Fields (Required in your flow)
#     full_name: str = Field(..., min_length=1, max_length=100, description="full_name of the account")
#     phone_number: str = Field(..., min_length=10, max_length=15)
#     email: EmailStr
#     pan: str
#     gstin: str
    
#     # Optional Fields (Matches your DB Model nullable fields)
#     company: Optional[str] = None
#     annual_revenue: Optional[Decimal] = Field(None, max_digits=15, decimal_places=2)
#     address: Optional[str] = None
#     city: Optional[str] = None
#     country: Optional[str] = None
#     industry: Optional[str] = None
#     description: Optional[str] = None
#     distributor_code: Optional[str] = None
#     business_status: Optional[str] = "New"

#     # Validators
#     @field_validator('full_name', 'phone_number', 'pan', 'gstin', 'company', 'city')
#     @classmethod
#     def clean_strings(cls, v):
#         if v:
#             return v.strip()
#         return v

#     @field_validator('phone_number')
#     @classmethod
#     def validate_phone(cls, v):
#         # Basic Regex for generic phone validation
#         if not re.match(r'^\+?1?\d{9,15}$', v):
#              raise ValueError('Invalid phone number format')
#         return v

# # --- INPUT MODEL (Client -> Server) ---
# class AccountCreate(AccountBase):
#     pass

# # --- OUTPUT MODEL (Server -> Client) ---
# class AccountResponse(AccountBase):
#     id: int
#     # DB uses 'full_name', but Schema uses 'name'. 
#     # We add full_name here so Pydantic can read the DB column directly.
#     full_name: str 
    
#     created_at: datetime
#     updated_at: datetime

#     # Config to read from SQLAlchemy Object
#     model_config = ConfigDict(from_attributes=True)





from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from typing import Optional, Dict, Any, Literal
from datetime import datetime

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
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: str = Field(..., min_length=10, max_length=15)
    
    # Workflow & Assignment (Optional)
    account_owner_id: Optional[str] = None
    account_status: Optional[AccountStatusType] = "Awareness"
    account_stage: Optional[AccountStageType] = "Initial Pitch"
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
    created_time: str
    modified_time: str

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

class AccountCreate(AccountBase):
    pass

class AccountResponse(AccountBase):
    id: int
    created_by: Optional[str]
    modified_by: Optional[str]
    created_time: datetime
    modified_time: datetime
    
    model_config = ConfigDict(from_attributes=True)

class GetAccountResponse(BaseModel):
    data: list[AccountResponse]
    page_info: Dict[str, Any]