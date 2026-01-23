from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, field_serializer, field_validator

from src.schemas.user import UserResponse


class ContactBase(BaseModel):
    # primary key
    id: str

    # Identity
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    designation: Optional[str] = None

    # relationship
    owner_id: str
    account_id: str
    modified_by_id: str
    created_by_id: str

    # time-capturing-fields
    modified_time: str
    created_time: str

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

    @field_validator("created_time", mode="after")
    @classmethod
    def parse_created_time(cls, value):
        if isinstance(value, str):
            date = datetime.fromisoformat(value)
            return datetime.fromisoformat(value)
        raise ValueError("created_time must be in string format")

    @field_validator("modified_time", mode="after")
    @classmethod
    def parse_modified_time(cls, value):
        if isinstance(value, str):
            dt = datetime.fromisoformat(value)
            return dt
        raise ValueError("modified_time must be in string format")

    @field_validator("modified_by_id", mode="after")
    @classmethod
    def parse_modified_by(cls, value):
        if isinstance(value, str):
            return int(value)
        raise ValueError("id must be in string format")

    @field_validator("created_by_id", mode="after")
    @classmethod
    def parse_created_by(cls, value):
        if isinstance(value, str):
            return int(value)
        raise ValueError("id must be in string format")

    @field_validator("id", mode="after")
    @classmethod
    def parse_id(cls, value):
        if isinstance(value, str):
            return int(value)
        raise ValueError("id must be in string format")

    @field_validator("account_id", mode="after")
    @classmethod
    def parse_account_id(cls, value):
        if isinstance(value, str):
            return int(value)
        raise ValueError("account_id must be in string format")

    @field_validator("owner_id", mode="after")
    @classmethod
    def parse_owner_id(cls, value):
        if isinstance(value, str):
            return int(value)
        raise ValueError("owner_id must be in string format")


class ContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Primary Identifier
    id: str

    # Identity
    first_name: str | None = None
    last_name: str | None = None
    designation: Optional[str] = None

    # Time capturing fields
    modified_time: datetime
    created_time: datetime

    # Communication
    email: EmailStr
    secondary_email: Any = None
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

    # Relationships
    created_by: UserResponse
    modified_by: UserResponse
    contact_owner: UserResponse
    parent_account: Any  # Can be a dict or a model

    # Flexible Fields
    custom_fields: Dict[str, Any] = {}

    @field_validator("id", mode="before")
    @classmethod
    def ensure_str(cls, v):
        """Ensures the top-level Contact ID is always a string."""
        return str(v) if v is not None else v

    @field_serializer("parent_account")
    def serialize_parent_account(self, value):
        """
        Handles conversion of parent_account regardless of whether it's
        a SQLAlchemy model or a dictionary from a JSON response.
        """
        if value is None:
            return None

        # Case 1: If it's a dictionary (like your example input)
        if isinstance(value, dict):
            # Convert known ID fields to string
            for key in ["id", "account_id", "owner_id"]:
                if key in value and value[key] is not None:
                    value[key] = str(value[key])
            return value

        # Case 2: If it's a SQLAlchemy model (checking for __dict__ or specific attributes)
        if hasattr(value, "id"):
            return {
                "id": str(value.id),
                "account_name": getattr(value, "account_name", None),
                "email": getattr(value, "email", None),
                "city": getattr(value, "city", None),
                "state": getattr(value, "state", None),
            }

        return value


class ContactResponseList(BaseModel):
    data: List[ContactResponse] = []
    page_info: dict[str, Any]
