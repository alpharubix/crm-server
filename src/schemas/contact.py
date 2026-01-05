from pydantic import BaseModel, ConfigDict, EmailStr,field_validator
from typing import Optional, Dict, Any
from datetime import datetime

class ContactBase(BaseModel):
    #primary key
    id:str

    # Identity
    first_name: str
    last_name: str 
    designation: Optional[str] = None

    #relationship
    owner_id: str
    account_id:str
    modified_by_id:str
    created_by_id:str

    #time-capturing-fields
    modified_time:str
    created_time:str

    email: EmailStr

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

    @field_validator('modified_by_id', mode='after')
    @classmethod
    def parse_modified_by(cls, value):
        if isinstance(value, str):
            return int(value)
        raise ValueError("id must be in string format")

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

    @field_validator('account_id', mode='after')
    @classmethod
    def parse_account_id(cls, value):
        if isinstance(value, str):
            return int(value)
        raise ValueError("account_id must be in string format")

    @field_validator('owner_id', mode='after')
    @classmethod
    def parse_owner_id(cls, value):
        if isinstance(value, str):
            return int(value)
        raise ValueError("owner_id must be in string format")


class ContactResponse(BaseModel):
    id: int
    last_name : str
    email: EmailStr
    model_config = ConfigDict(from_attributes=True)

    @field_validator('id')
    @classmethod
    def parse_id(cls, value):
        if isinstance(value, int):
            return str(value)
        return value