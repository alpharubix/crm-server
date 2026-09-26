from datetime import datetime
from typing import Optional, List, Union
from pydantic import BaseModel, Field


class SupportTicketCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    service: str = Field(default="General Technical Issue")
    priority: str = Field(default="Medium")
    attachment_links: Optional[Union[List[str], str]] = Field(default_factory=list)
    attachment_link: Optional[Union[List[str], str]] = None


class SupportTicketStatusUpdate(BaseModel):
    status: str


class SupportTicketUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    service: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    attachment_links: Optional[Union[List[str], str]] = None
    attachment_link: Optional[Union[List[str], str]] = None


class SupportTicketResponse(BaseModel):
    id: int
    ticket_id: str
    user_id: int
    title: str
    service: str
    priority: str
    description: str
    status: str
    attachment_links: Optional[List[str]] = []
    updated_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

