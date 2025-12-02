from pydantic import BaseModel, EmailStr, field_validator, Field, ConfigDict
import re

# --- INPUT MODEL ---
class LeadrCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    phone_number: str = Field(..., min_length=10, max_length=15)
    email: EmailStr
    pan: str
    gstin: str

    @field_validator('name', 'phone_number')
    @classmethod
    def clean_data(cls, v):
        v = v.strip()
        if not v:
            raise ValueError('Field cannot be empty/blank')
        return v
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v):
        if not re.match(r'^\+?1?\d{9,15}$', v):
             raise ValueError('Invalid phone number format')
        return v

# --- OUTPUT MODEL ---
class LeadResponse(BaseModel):
    id: int
    name: str
    phone_number: str
    email: EmailStr
    pan: str
    gstin: str

    # Pydantic V2 replacement for "class Config: orm_mode = True"
    model_config = ConfigDict(from_attributes=True)

