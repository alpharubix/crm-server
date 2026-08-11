from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from src.database import get_db, get_mongodb
from src.schemas.account_task import (
    AccountTaskCreate,
    BulkAccountTaskCreate,
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

@router.post(
    "/account-tasks/bulk",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
def bulk_create_tasks(
    request: Request,
    bulk_in: BulkAccountTaskCreate,
    db: Session = Depends(get_db),
):
    current_user_id = getattr(request.state, "user_id", 1)
    return controller.bulk_create_account_tasks(db=db, bulk_in=bulk_in, current_user_id=int(current_user_id))

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
    account_owner_id: Optional[List[int]] = Query(None),
    source_type: Optional[List[str]] = Query(None),
    account_stage: Optional[List[str]] = Query(None),
    business_status: Optional[List[str]] = Query(None),
    waba_interested: Optional[str] = Query(None),
    is_priority_account: Optional[str] = Query(None),
    cb_condition: Optional[str] = Query(None),
    cb_users: Optional[List[int]] = Query(None),
    cb_date_condition: Optional[str] = Query(None),
    cb_from_date: Optional[str] = Query(None),
    cb_to_date: Optional[str] = Query(None),
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
        account_owner_id=account_owner_id,
        source_type=source_type,
        account_stage=account_stage,
        business_status=business_status,
        waba_interested=waba_interested,
        is_priority_account=is_priority_account,
        cb_condition=cb_condition,
        cb_users=cb_users,
        cb_date_condition=cb_date_condition,
        cb_from_date=cb_from_date,
        cb_to_date=cb_to_date,
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
