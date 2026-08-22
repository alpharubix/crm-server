from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from src.controllers import account_task as controller
from src.database import get_db, get_mongodb
from src.schemas.account_task import (
    AccountTaskCreate,
    AccountTaskListResponse,
    AccountTaskUpdate,
    BulkAccountTaskCreate,
    BulkTaskStatusUpdate,
)

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
    return controller.create_account_task(
        db=db, task_in=task_in, current_user_id=int(current_user_id)
    )


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
    return controller.bulk_create_account_tasks(
        db=db, bulk_in=bulk_in, current_user_id=int(current_user_id)
    )


@router.put(
    "/account-tasks/bulk-status",
    response_model=dict,
)
def bulk_update_task_status(
    request: Request,
    payload: BulkTaskStatusUpdate,
    db: Session = Depends(get_db),
):
    current_user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "role", None)
    return controller.bulk_update_task_status(
        db=db,
        task_ids=payload.task_ids,
        new_status=payload.task_status,
        current_user_id=int(current_user_id)
        if current_user_id and str(current_user_id).isdigit()
        else None,
        current_role=user_role,
    )


@router.get(
    "/account-tasks",
    response_model=AccountTaskListResponse,
)
def list_tasks(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    account_id: str | int | None = Query(None),
    task_status: str | None = Query(None),
    task_type: str | None = Query(None),
    call_back_status: str | None = Query(None),
    search: str | None = Query(None),
    assigned_to_id: str | int | None = Query(None),
    account_owner_id: list[str] | list[int] | str | int | None = Query(None),
    source_type: list[str] | None = Query(None),
    account_stage: list[str] | None = Query(None),
    business_status: list[str] | None = Query(None),
    waba_interested: str | None = Query(None),
    is_priority_account: str | None = Query(None),
    cb_condition: str | None = Query(None),
    cb_users: list[str] | list[int] | str | int | None = Query(None),
    cb_date_condition: str | None = Query(None),
    cb_from_date: str | None = Query(None),
    cb_to_date: str | None = Query(None),
    assigned_date_condition: str | None = Query(None),
    assigned_from_date: str | None = Query(None),
    assigned_to_date: str | None = Query(None),
    created_from_date: str | None = Query(None),
    created_to_date: str | None = Query(None),
    assignment_from_date: str | None = Query(None),
    assignment_to_date: str | None = Query(None),
    note_from_date: str | None = Query(None),
    note_to_date: str | None = Query(None),
    db: Session = Depends(get_db),
    mongodb=Depends(get_mongodb),
):
    user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "role", None)
    return controller.get_account_tasks(
        db=db,
        mongodb=mongodb,
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
        assigned_date_condition=assigned_date_condition,
        assigned_from_date=assigned_from_date,
        assigned_to_date=assigned_to_date,
        created_from_date=created_from_date,
        created_to_date=created_to_date,
        assignment_from_date=assignment_from_date,
        assignment_to_date=assignment_to_date,
        note_from_date=note_from_date,
        note_to_date=note_to_date,
        user_id=int(user_id) if user_id and str(user_id).isdigit() else user_id,
        user_role=user_role,
    )


@router.get(
    "/account-tasks/{task_id}",
    response_model=dict,
)
def get_task(
    request: Request,
    task_id: str,
    db: Session = Depends(get_db),
    mongodb=Depends(get_mongodb),
):
    user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "role", None)
    return controller.get_account_task_by_id(
        db=db,
        task_id=task_id,
        mongodb=mongodb,
        user_id=int(user_id) if user_id and str(user_id).isdigit() else user_id,
        user_role=user_role,
    )


@router.put(
    "/account-tasks/{task_id}",
    response_model=dict,
)
def update_task(
    request: Request,
    task_id: str,
    task_in: AccountTaskUpdate,
    db: Session = Depends(get_db),
):
    current_user_id = getattr(request.state, "user_id", 1)
    user_role = getattr(request.state, "role", None)
    return controller.update_account_task(
        db=db,
        task_id=task_id,
        task_in=task_in,
        current_user_id=int(current_user_id)
        if str(current_user_id).isdigit()
        else current_user_id,
        user_role=user_role,
    )


@router.delete(
    "/account-tasks/{task_id}",
    response_model=dict,
)
def delete_task(
    request: Request,
    task_id: str,
    db: Session = Depends(get_db),
):
    current_user_id = getattr(request.state, "user_id", 1)
    user_role = getattr(request.state, "role", None)
    return controller.delete_account_task(
        db=db,
        task_id=task_id,
        current_user_id=int(current_user_id)
        if str(current_user_id).isdigit()
        else current_user_id,
        user_role=user_role,
    )


@router.get(
    "/accounts/{account_id}/tasks",
    response_model=AccountTaskListResponse,
)
def list_tasks_for_account(
    request: Request,
    account_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "role", None)
    return controller.get_account_tasks(
        db=db,
        page=page,
        page_size=page_size,
        account_id=account_id,
        user_id=int(user_id) if user_id and str(user_id).isdigit() else user_id,
        user_role=user_role,
    )
