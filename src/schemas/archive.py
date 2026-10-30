from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict


class ArchiveRequest(BaseModel):
    reason: Optional[str] = None


class ArchiveActionResponse(BaseModel):
    success: bool
    message: str
    id: int
    module: str
    archived_at: Optional[datetime] = None


class RestoreActionResponse(BaseModel):
    success: bool
    message: str
    id: int
    module: str


class ArchivedItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: Optional[str] = None
    module: str
    archived_at: datetime
    archived_by_id: Optional[int] = None
    archived_by_name: Optional[str] = None
    details: Optional[dict[str, Any]] = None


class ArchivedListResponse(BaseModel):
    success: bool
    data: List[ArchivedItem]
    total_count: int
    page: int
    page_size: int
    total_pages: int
