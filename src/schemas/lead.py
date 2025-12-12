from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from typing import Optional
from datetime import datetime
from decimal import Decimal
import re

# --- SHARED PROPERTIES ---
# Fields that can exist in both Input (Create) and Output (Read)
class LeadBase(BaseModel):
    # Critical Fields (Required in your flow)
    full_name: str = Field(..., min_length=1, max_length=100, description="full_name of the lead")
    phone_number: str = Field(..., min_length=10, max_length=15)
    email: EmailStr
    pan: str
    gstin: str
    
    # Optional Fields (Matches your DB Model nullable fields)
    company: Optional[str] = None
    annual_revenue: Optional[Decimal] = Field(None, max_digits=15, decimal_places=2)
    address: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    distributor_code: Optional[str] = None
    business_status: Optional[str] = "New"

    # Validators
    @field_validator('full_name', 'phone_number', 'pan', 'gstin', 'company', 'city')
    @classmethod
    def clean_strings(cls, v):
        if v:
            return v.strip()
        return v

    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        # Basic Regex for generic phone validation
        if not re.match(r'^\+?1?\d{9,15}$', v):
             raise ValueError('Invalid phone number format')
        return v

# --- INPUT MODEL (Client -> Server) ---
class LeadCreate(LeadBase):
    pass

# --- OUTPUT MODEL (Server -> Client) ---
class LeadResponse(LeadBase):
    id: int
    # DB uses 'full_name', but Schema uses 'name'. 
    # We add full_name here so Pydantic can read the DB column directly.
    full_name: str 
    
    created_at: datetime
    updated_at: datetime

    # Config to read from SQLAlchemy Object
    model_config = ConfigDict(from_attributes=True)