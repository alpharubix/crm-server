from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import math
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, status
from sqlalchemy import or_, and_, desc, not_
from sqlalchemy.orm import Session, joinedload

from src.models.account_task import AccountTask, get_call_back_info
from src.models.account import Account
from src.models.user import User
from src.schemas.account_task import AccountTaskCreate, AccountTaskUpdate, BulkAccountTaskCreate
from src.controllers.audit_log import log_action
from src.controllers.notes import get_notes

IST = ZoneInfo("Asia/Kolkata")

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

    task = AccountTask(
        company_id=1,
        module_name=task_in.module_name or "Account",
        account_id=task_in.account_id,
        task_type=task_in.task_type,
        task_description=task_in.task_description or "",
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

    created_tasks = []

    accounts = db.query(Account).filter(
        Account.id.in_(bulk_in.account_ids),
        or_(Account.company_id == 1, Account.company_id.is_(None))
    ).all()
    account_map = {acc.id: acc for acc in accounts}

    now = datetime.now(timezone.utc)
    assigned_dt = bulk_in.task_assigned_date_time or now

    for acc_id in bulk_in.account_ids:
        account = account_map.get(acc_id)
        if not account:
            continue

        task = AccountTask(
            company_id=1,
            module_name="Account",
            account_id=acc_id,
            task_type="Update Record",
            task_description=bulk_in.task_description or "",
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
        "message": f"Successfully created {len(created_tasks)} task(s) for {len(accounts)} account(s)",
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
    account_owner_id: Optional[List[int]] = None,
    # New Account Filters
    source_type: Optional[List[str]] = None,
    account_stage: Optional[List[str]] = None,
    business_status: Optional[List[str]] = None,
    waba_interested: Optional[str] = None,
    is_priority_account: Optional[str] = None,
    # Advanced Call Back Filter Section
    cb_condition: Optional[str] = None,
    cb_users: Optional[List[int]] = None,
    cb_date_condition: Optional[str] = None,
    cb_from_date: Optional[str] = None,
    cb_to_date: Optional[str] = None,
):
    query = db.query(AccountTask).options(
        joinedload(AccountTask.account).joinedload(Account.owner),
        joinedload(AccountTask.assigned_to)
    ).filter(or_(AccountTask.company_id == 1, AccountTask.company_id.is_(None)))

    effective_cb_date = cb_date_condition or (call_back_status if call_back_status != "all" else None)
    effective_cb_cond = cb_condition or "Is"

    needs_account_join = bool(
        account_owner_id or source_type or account_stage or business_status or waba_interested or is_priority_account
        or effective_cb_cond or cb_users or effective_cb_date or cb_from_date or cb_to_date or search
    )

    if needs_account_join:
        query = query.join(AccountTask.account)

    if account_id:
        query = query.filter(AccountTask.account_id == account_id)
    if task_status:
        query = query.filter(AccountTask.task_status == task_status)
    if task_type:
        query = query.filter(AccountTask.task_type == task_type)
    if assigned_to_id:
        query = query.filter(AccountTask.assigned_to_id == assigned_to_id)
    if account_owner_id:
        owner_ids = [int(u) for u in (account_owner_id if isinstance(account_owner_id, list) else [account_owner_id]) if str(u).isdigit()]
        if owner_ids:
            query = query.filter(Account.account_owner_id.in_(owner_ids))
    if search:
        query = query.filter(
            or_(
                AccountTask.task_description.ilike(f"%{search}%"),
                AccountTask.task_type.ilike(f"%{search}%"),
                Account.account_name.ilike(f"%{search}%")
            )
        )

    # General Account Filters
    if source_type:
        query = query.filter(Account.source_type.in_(source_type))
    if account_stage:
        query = query.filter(Account.account_stage.in_(account_stage))
    if business_status:
        query = query.filter(Account.business_status.in_(business_status))
    if waba_interested and waba_interested in ["Yes", "No"]:
        waba_bool = True if waba_interested == "Yes" else False
        query = query.filter(Account.waba_interested == waba_bool)
    if is_priority_account and is_priority_account in ["Yes", "No"]:
        query = query.filter(Account.is_priority_account == is_priority_account)

    # Advanced Call Back Date/Time Filter Section
    cb_clauses = []
    if cb_users:
        cb_clauses.append(
            or_(
                AccountTask.assigned_to_id.in_(cb_users),
                Account.account_owner_id.in_(cb_users)
            )
        )

    if effective_cb_date:
        now_utc = datetime.now(timezone.utc)
        now_ist = now_utc.astimezone(IST)
        today_start = datetime(now_ist.year, now_ist.month, now_ist.day, 0, 0, 0, tzinfo=IST)
        today_end = datetime(now_ist.year, now_ist.month, now_ist.day, 23, 59, 59, tzinfo=IST)

        if effective_cb_date == "Blank":
            cb_clauses.append(Account.call_back_date_time.is_(None))
        elif effective_cb_date == "Overdue":
            cb_clauses.append(and_(Account.call_back_date_time.isnot(None), Account.call_back_date_time < today_start))
        elif effective_cb_date == "Due Today":
            cb_clauses.append(Account.call_back_date_time.between(today_start, today_end))
        elif effective_cb_date == "Due Tomorrow":
            tomorrow_start = today_start + timedelta(days=1)
            tomorrow_end = today_end + timedelta(days=1)
            cb_clauses.append(Account.call_back_date_time.between(tomorrow_start, tomorrow_end))
        elif effective_cb_date == "Due This Week":
            weekday = today_start.weekday()
            start_of_week = today_start - timedelta(days=weekday)
            end_of_week = today_start + timedelta(days=(6 - weekday), hours=23, minutes=59, seconds=59)
            cb_clauses.append(Account.call_back_date_time.between(start_of_week, end_of_week))
        elif effective_cb_date == "Due Next Week":
            weekday = today_start.weekday()
            start_of_next_week = today_start + timedelta(days=(7 - weekday))
            end_of_next_week = start_of_next_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
            cb_clauses.append(Account.call_back_date_time.between(start_of_next_week, end_of_next_week))
        elif effective_cb_date == "Due Dates" and cb_from_date and cb_to_date:
            try:
                f_dt = datetime.strptime(cb_from_date, "%Y-%m-%d").replace(tzinfo=IST)
                t_dt = datetime.strptime(cb_to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=IST)
                cb_clauses.append(Account.call_back_date_time.between(f_dt, t_dt))
            except Exception:
                pass

    if cb_clauses:
        combined_clause = and_(*cb_clauses)
        if effective_cb_cond == "Not":
            query = query.filter(not_(combined_clause))
        else:
            query = query.filter(combined_clause)

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

        results.append(task_to_dict(task))

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
    ).filter(
        AccountTask.id == task_id,
        or_(AccountTask.company_id == 1, AccountTask.company_id.is_(None))
    ).first()

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
    task = db.query(AccountTask).filter(
        AccountTask.id == task_id,
        or_(AccountTask.company_id == 1, AccountTask.company_id.is_(None))
    ).first()
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
    task = db.query(AccountTask).filter(
        AccountTask.id == task_id,
        or_(AccountTask.company_id == 1, AccountTask.company_id.is_(None))
    ).first()
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
