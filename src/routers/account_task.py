from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from src.database import get_db, get_mongodb
from src.schemas.account_task import (
    AccountTaskCreate,
    AccountTaskUpdate,
    AccountTaskSchema,
    AccountTaskListResponse,
)
from src.controllers import account_task as controller

router = APIRouter(tags=["Account Tasks"])

@router.post(
    "/account-tasks",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
def create_task(
    request: Request,
    task_in: AccountTaskCreate,
    db: Session = Depends(get_db),
):
    current_user_id = getattr(request.state, "user_id", 1)
    return controller.create_account_task(db=db, task_in=task_in, current_user_id=int(current_user_id))

@router.get(
    "/account-tasks",
    response_model=AccountTaskListResponse,
)
def list_tasks(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    account_id: Optional[int] = Query(None),
    task_status: Optional[str] = Query(None),
    task_type: Optional[str] = Query(None),
    call_back_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    assigned_to_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    return controller.get_account_tasks(
        db=db,
        page=page,
        page_size=page_size,
        account_id=account_id,
        task_status=task_status,
        task_type=task_type,
        call_back_status=call_back_status,
        search=search,
        assigned_to_id=assigned_to_id,
    )

@router.get(
    "/account-tasks/{task_id}",
    response_model=dict,
)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    mongodb = Depends(get_mongodb),
):
    return controller.get_account_task_by_id(db=db, task_id=task_id, mongodb=mongodb)

@router.put(
    "/account-tasks/{task_id}",
    response_model=dict,
)
def update_task(
    request: Request,
    task_id: int,
    task_in: AccountTaskUpdate,
    db: Session = Depends(get_db),
):
    current_user_id = getattr(request.state, "user_id", 1)
    return controller.update_account_task(
        db=db, task_id=task_id, task_in=task_in, current_user_id=int(current_user_id)
    )

@router.delete(
    "/account-tasks/{task_id}",
    response_model=dict,
)
def delete_task(
    request: Request,
    task_id: int,
    db: Session = Depends(get_db),
):
    current_user_id = getattr(request.state, "user_id", 1)
    return controller.delete_account_task(
        db=db, task_id=task_id, current_user_id=int(current_user_id)
    )

@router.get(
    "/accounts/{account_id}/tasks",
    response_model=AccountTaskListResponse,
)
def list_tasks_for_account(
    account_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return controller.get_account_tasks(
        db=db,
        page=page,
        page_size=page_size,
        account_id=account_id,
    )
