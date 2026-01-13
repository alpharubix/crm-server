from pydantic import BaseModel, field_validator


class Note(BaseModel):
    id: str
    note: str
    @field_validator('id',mode='after')
    @classmethod
    def validate_note_id(cls, v):
        if isinstance(v,int):
            return str(v)
        return v
