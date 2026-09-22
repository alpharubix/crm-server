from datetime import datetime
from zipfile import BadZipfile

from pydantic import BaseModel, field_validator, field_serializer
from pymongo.cursor import List


class ExistingUser(BaseModel):
    id: str
    full_name: str
    email: str
    # created_time: str
    # modified_time: str
    zuid: str
    role: str
    # profile: str
    created_by_id: str | int = None
    modified_by_id: str | int = None

    # @field_validator("created_time", mode="after")
    # @classmethod
    # def parse_created_time(cls, value):
    #     if isinstance(value, str):
    #         date = datetime.fromisoformat(value)
    #         return datetime.fromisoformat(value)
    #     raise ValueError("created_time must be in string format")

    # @field_validator("modified_time", mode="after")
    # @classmethod
    # def parse_modified_time(cls, value):
    #     if isinstance(value, str):
    #         dt = datetime.fromisoformat(value)
    #         return dt
    #     raise ValueError("modified_time must be in string format")

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


class UserResponse(BaseModel):
    id: str
    name: str

    @field_validator("id", mode="before")
    @classmethod
    def cast_id_to_str(cls, value):
        return str(value) if value is not None else None


class UserFilterMode(BaseModel):
    id: str
    full_name: str

    @field_validator("id", mode="before")
    @classmethod
    def parse_id(cls, value):
        return str(value)

class UserResponseList(BaseModel):
    data: List[UserResponse] =[]

class UserFilterResponse(BaseModel):
    data: List[UserFilterMode] = []

class UserResponseAccount(BaseModel):
    id: str | None = None
    full_name: str
    email: str

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def parse_id(cls, value):
        return str(value) if value is not None else None
