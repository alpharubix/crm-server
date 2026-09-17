from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from src.controllers import deal_task as controller
from src.database import get_db, get_mongodb
from src.schemas.deal_task import (
    BulkDealTaskCreate,
    BulkDealTaskStatusUpdate,
    DealTaskCreate,
    DealTaskListResponse,
    DealTaskUpdate,
)

router = APIRouter(tags=["Deal Tasks"])


@router.post(
    "/deal-tasks",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
def create_task(
    request: Request,
    task_in: DealTaskCreate,
    db: Session = Depends(get_db),
):
    current_user_id = getattr(request.state, "user_id", 1)
    return controller.create_deal_task(
        db=db, task_in=task_in, current_user_id=int(current_user_id)
    )


@router.post(
    "/deal-tasks/bulk",
    status_code=status.HTTP_201_CREATED,
    response_model=dict,
)
def bulk_create_tasks(
    request: Request,
    bulk_in: BulkDealTaskCreate,
    db: Session = Depends(get_db),
):
    current_user_id = getattr(request.state, "user_id", 1)
    return controller.bulk_create_deal_tasks(
        db=db, bulk_in=bulk_in, current_user_id=int(current_user_id)
    )


@router.put(
    "/deal-tasks/bulk-status",
    response_model=dict,
)
def bulk_update_task_status(
    request: Request,
    payload: BulkDealTaskStatusUpdate,
    db: Session = Depends(get_db),
):
    current_user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "role", None)
    return controller.bulk_update_deal_task_status(
        db=db,
        task_ids=payload.task_ids,
        new_status=payload.task_status,
        current_user_id=int(current_user_id)
        if current_user_id and str(current_user_id).isdigit()
        else None,
        current_role=user_role,
    )


@router.get(
    "/deal-tasks",
    response_model=DealTaskListResponse,
)
def list_tasks(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    deal_id: str | int | None = Query(None),
    account_id: str | int | None = Query(None),
    task_status: str | None = Query(None),
    task_type: str | None = Query(None),
    call_back_status: str | None = Query(None),
    search: str | None = Query(None),
    assigned_to_id: str | int | None = Query(None),
    deal_owner_id: list[str] | list[int] | str | int | None = Query(None),
    loan_type: list[str] | None = Query(None),
    deal_stage: list[str] | None = Query(None),
    deal_status: list[str] | None = Query(None),
    lender_name: list[str] | None = Query(None),
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
    db: Session = Depends(get_db),
    mongodb=Depends(get_mongodb),
):
    user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "role", None)
    return controller.get_deal_tasks(
        db=db,
        mongodb=mongodb,
        page=page,
        page_size=page_size,
        deal_id=int(deal_id) if deal_id and str(deal_id).isdigit() else deal_id,
        account_id=int(account_id)
        if account_id and str(account_id).isdigit()
        else account_id,
        task_status=task_status,
        task_type=task_type,
        call_back_status=call_back_status,
        search=search,
        assigned_to_id=int(assigned_to_id)
        if assigned_to_id and str(assigned_to_id).isdigit()
        else assigned_to_id,
        deal_owner_id=deal_owner_id,
        loan_type=loan_type,
        deal_stage=deal_stage,
        deal_status=deal_status,
        lender_name=lender_name,
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
        user_id=int(user_id) if user_id and str(user_id).isdigit() else user_id,
        user_role=user_role,
    )


@router.get(
    "/deal-tasks/{task_id}",
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
    return controller.get_deal_task_by_id(
        db=db,
        task_id=task_id,
        mongodb=mongodb,
        user_id=int(user_id) if user_id and str(user_id).isdigit() else user_id,
        user_role=user_role,
    )


@router.put(
    "/deal-tasks/{task_id}",
    response_model=dict,
)
def update_task(
    request: Request,
    task_id: str,
    task_in: DealTaskUpdate,
    db: Session = Depends(get_db),
):
    current_user_id = getattr(request.state, "user_id", 1)
    user_role = getattr(request.state, "role", None)
    return controller.update_deal_task(
        db=db,
        task_id=task_id,
        task_in=task_in,
        current_user_id=int(current_user_id)
        if str(current_user_id).isdigit()
        else current_user_id,
        user_role=user_role,
    )


@router.get(
    "/deals/{deal_id}/tasks",
    response_model=DealTaskListResponse,
)
def list_tasks_for_deal(
    request: Request,
    deal_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    user_id = getattr(request.state, "user_id", None)
    user_role = getattr(request.state, "role", None)
    return controller.get_deal_tasks(
        db=db,
        page=page,
        page_size=page_size,
        deal_id=int(deal_id) if str(deal_id).isdigit() else deal_id,
        user_id=int(user_id) if user_id and str(user_id).isdigit() else user_id,
        user_role=user_role,
    )
