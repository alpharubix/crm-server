from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Optional
from datetime import datetime

class ContactBase(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

# Input (Create)
class ContactCreate(ContactBase):
    # CRITICAL: We need to know who this person belongs to
    account_id: int 

# Output (Read)
class ContactResponse(ContactBase):
    id: int
    account_id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

