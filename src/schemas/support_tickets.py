from datetime import datetime
from pydantic import BaseModel, Field


class SupportTicketCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    service: str = Field(default="General Technical Issue")
    priority: str = Field(default="Medium")


class SupportTicketStatusUpdate(BaseModel):
    status: str


class SupportTicketResponse(BaseModel):
    id: int
    ticket_id: str
    user_id: int
    title: str
    service: str
    priority: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

