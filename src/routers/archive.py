from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from src.controllers import archive as archive_controller
from src.database import get_db
from src.schemas.archive import (
    ArchiveActionResponse,
    ArchivedListResponse,
    ArchiveRequest,
    RestoreActionResponse,
)

router = APIRouter(prefix="/archive", tags=["archive"])


@router.get("/{module}", response_model=ArchivedListResponse)
def get_archived_records(
    module: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    user_role = getattr(request.state, "role", None)
    return archive_controller.get_archived_list(
        db=db,
        module=module,
        user_role=user_role,
        page=page,
        page_size=page_size,
        search=search,
    )


@router.post("/{module}/{record_id}", response_model=ArchiveActionResponse)
def archive_record(
    module: str,
    record_id: int,
    request: Request,
    body: ArchiveRequest = ArchiveRequest(),
    db: Session = Depends(get_db),
):
    user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "role", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return archive_controller.archive_record(
        db=db,
        module=module,
        record_id=record_id,
        user_id=int(user_id),
        user_role=user_role or "user",
        reason=body.reason,
    )


@router.post("/{module}/{record_id}/restore", response_model=RestoreActionResponse)
def restore_record(
    module: str,
    record_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "role", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return archive_controller.restore_record(
        db=db,
        module=module,
        record_id=record_id,
        user_id=int(user_id),
        user_role=user_role or "user",
    )
