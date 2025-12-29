from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime

class ContactBase(BaseModel):
    # Identity
    first_name: str
    last_name: str 
    designation: Optional[str] = None

    # Communication
    email: EmailStr
    secondary_email: Optional[EmailStr] = None
    mobile: Optional[str] = None
    phone: Optional[str] = None

    # Business
    lead_source: Optional[str] = None

    # Address
    street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    pincode: Optional[str] = None

    # Flexible Fields (JSONB)
    custom_fields: Dict[str, Any] = {}

# Input (Create)
class ContactCreate(ContactBase):
    # CRITICAL: We need to know who this person belongs to
    account_id: int
    account_owner: int 

# Output (Read)
class ContactResponse(ContactBase):
    id: int
    account_id: int
    
    # System Audit
    created_by: Optional[str] = None
    modified_by: Optional[str] = None
    created_time: datetime
    modified_time: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)