from pydantic import BaseModel, field_validator


class Note(BaseModel):
    id: int
    note: str
    @field_validator('id')
    @classmethod
    def validate_note_id(cls, v):
        if isinstance(v,str):
            return int(v)
        return v
