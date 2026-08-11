from datetime import datetime, timezone
import math
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from sqlalchemy import or_, and_, desc
from sqlalchemy.orm import Session, joinedload

from src.models.account_task import AccountTask, get_call_back_info
from src.models.account import Account
from src.models.user import User
from src.schemas.account_task import AccountTaskCreate, AccountTaskUpdate, BulkAccountTaskCreate
from src.controllers.audit_log import log_action
from src.controllers.notes import get_notes

def task_to_dict(task: AccountTask) -> Dict[str, Any]:
    # Check if task is overdue based on due date
    effective_status = task.computed_task_status
    
    assigned_id = task.assigned_to_id or task.account_owner_id
    assigned_name = None
    if task.assigned_to:
        assigned_name = task.assigned_to.full_name or task.assigned_to.email
    elif task.account and task.account.owner:
        assigned_name = task.account.owner.full_name or task.account.owner.email

    return {
        "id": task.id,
        "module_name": task.module_name or "Account",
        "account_id": task.account_id,
        "account_name": task.account_name,
        "account_owner": task.account_owner,
        "account_owner_id": task.account_owner_id,
        "account_status": task.account_status,
        "account_stage": task.account_stage,
        "call_back_date_status": task.call_back_date_status,
        "task_type": task.task_type,
        "task_description": task.task_description,
        "task_assigned_date_time": task.task_assigned_date_time,
        "task_due_date_time": task.task_due_date_time,
        "task_status": effective_status,
        "assigned_to_id": assigned_id,
        "assigned_to_name": assigned_name,
        "created_by_id": task.created_by_id,
        "modified_by_id": task.modified_by_id,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }

def create_account_task(db: Session, task_in: AccountTaskCreate, current_user_id: int):
    account = db.query(Account).filter(Account.id == task_in.account_id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with ID {task_in.account_id} not found",
        )

    description = task_in.task_description
    if task_in.task_type == "Call" and not description:
        _, call_desc = get_call_back_info(account.call_back_date_time)
        description = call_desc

    task = AccountTask(
        module_name=task_in.module_name or "Account",
        account_id=task_in.account_id,
        task_type=task_in.task_type,
        task_description=description or "",
        task_assigned_date_time=task_in.task_assigned_date_time or datetime.now(timezone.utc),
        task_due_date_time=task_in.task_due_date_time,
        task_status=task_in.task_status or "Unassigned",
        assigned_to_id=task_in.assigned_to_id or account.account_owner_id,
        created_by_id=current_user_id,
        modified_by_id=current_user_id,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    log_action(
        db,
        current_user_id,
        "USER",
        "CREATED",
        "AccountTask",
        task.id,
        {"account_id": task.account_id, "task_type": task.task_type, "task_status": task.task_status},
    )

    return task_to_dict(task)

def bulk_create_account_tasks(db: Session, bulk_in: BulkAccountTaskCreate, current_user_id: int):
    if not bulk_in.account_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No account IDs provided for bulk creation",
        )

    task_types = ["Call", "Update Record", "Email", "Move Status"]
    created_tasks = []

    accounts = db.query(Account).filter(Account.id.in_(bulk_in.account_ids)).all()
    account_map = {acc.id: acc for acc in accounts}

    now = datetime.now(timezone.utc)
    assigned_dt = bulk_in.task_assigned_date_time or now

    for acc_id in bulk_in.account_ids:
        account = account_map.get(acc_id)
        if not account:
            continue

        _, call_desc = get_call_back_info(account.call_back_date_time)

        for t_type in task_types:
            desc_val = call_desc if t_type == "Call" else (bulk_in.task_description or "")

            task = AccountTask(
                module_name="Account",
                account_id=acc_id,
                task_type=t_type,
                task_description=desc_val,
                task_assigned_date_time=assigned_dt,
                task_due_date_time=bulk_in.task_due_date_time,
                task_status=bulk_in.task_status or "Unassigned",
                assigned_to_id=account.account_owner_id,
                created_by_id=current_user_id,
                modified_by_id=current_user_id,
            )
            db.add(task)
            created_tasks.append(task)

    db.commit()

    log_action(
        db,
        current_user_id,
        "USER",
        "BULK_CREATED",
        "AccountTask",
        0,
        {
            "account_ids": bulk_in.account_ids,
            "tasks_count": len(created_tasks),
        },
    )

    return {
        "message": f"Successfully created {len(created_tasks)} tasks for {len(accounts)} account(s)",
        "tasks_created": len(created_tasks),
        "accounts_count": len(accounts),
    }

def get_account_tasks(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    account_id: Optional[int] = None,
    task_status: Optional[str] = None,
    task_type: Optional[str] = None,
    call_back_status: Optional[str] = None,
    search: Optional[str] = None,
    assigned_to_id: Optional[int] = None,
):
    query = db.query(AccountTask).options(
        joinedload(AccountTask.account).joinedload(Account.owner),
        joinedload(AccountTask.assigned_to)
    )

    if account_id:
        query = query.filter(AccountTask.account_id == account_id)
    if task_status:
        query = query.filter(AccountTask.task_status == task_status)
    if task_type:
        query = query.filter(AccountTask.task_type == task_type)
    if assigned_to_id:
        query = query.filter(AccountTask.assigned_to_id == assigned_to_id)
    if search:
        query = query.join(AccountTask.account).filter(
            or_(
                AccountTask.task_description.ilike(f"%{search}%"),
                AccountTask.task_type.ilike(f"%{search}%"),
                Account.account_name.ilike(f"%{search}%")
            )
        )

    total_records = query.count()
    total_pages = math.ceil(total_records / page_size) if page_size > 0 else 1

    offset = (page - 1) * page_size
    tasks = query.order_by(desc(AccountTask.created_at)).offset(offset).limit(page_size).all()

    results = []
    now = datetime.now(timezone.utc)

    for task in tasks:
        if task.task_due_date_time and task.task_status not in ["Completed", "Verified"]:
            due = task.task_due_date_time
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            if due < now and task.task_status != "Overdue":
                task.task_status = "Overdue"
                db.add(task)
                db.commit()

        task_data = task_to_dict(task)
        if call_back_status and call_back_status != "all":
            if task_data.get("call_back_date_status") != call_back_status:
                continue
        results.append(task_data)

    return {
        "data": results,
        "page_info": {
            "page": page,
            "total_pages": total_pages,
            "total_records": total_records,
        },
    }

def get_account_task_by_id(db: Session, task_id: int, mongodb: Optional[Any] = None):
    task = db.query(AccountTask).options(
        joinedload(AccountTask.account).joinedload(Account.owner),
        joinedload(AccountTask.assigned_to)
    ).filter(AccountTask.id == task_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account Task with ID {task_id} not found",
        )
    
    task_dict = task_to_dict(task)
    if mongodb is not None:
        try:
            notes = get_notes(
                id_list=[str(task_id)],
                notes_collection=mongodb["Notes"],
                module_name=["Account_Tasks", "AccountTask", "AccountTasks", "Account Task"],
            )
            task_dict["notes"] = notes
        except Exception:
            task_dict["notes"] = []
    else:
        task_dict["notes"] = []

    return task_dict

def update_account_task(db: Session, task_id: int, task_in: AccountTaskUpdate, current_user_id: int):
    task = db.query(AccountTask).filter(AccountTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account Task with ID {task_id} not found",
        )

    update_data = task_in.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(task, field, val)

    task.modified_by_id = current_user_id
    task.updated_at = datetime.now(timezone.utc)

    db.add(task)
    db.commit()
    db.refresh(task)

    log_action(
        db,
        current_user_id,
        "USER",
        "UPDATED",
        "AccountTask",
        task.id,
        update_data,
    )

    return task_to_dict(task)

def delete_account_task(db: Session, task_id: int, current_user_id: int):
    task = db.query(AccountTask).filter(AccountTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account Task with ID {task_id} not found",
        )

    db.delete(task)
    db.commit()

    log_action(
        db,
        current_user_id,
        "USER",
        "DELETED",
        "AccountTask",
        task_id,
        {},
    )
    return {"message": "Account Task deleted successfully"}
