import calendar
import math
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, not_, or_
from sqlalchemy.orm import Session, joinedload

from src.controllers.audit_log import log_action
from src.controllers.auth import MANAGERID
from src.controllers.notes import get_notes
from src.models.account import Account
from src.models.account_task import AccountTask
from src.models.user import User
from src.schemas.account_task import (
    AccountTaskCreate,
    AccountTaskUpdate,
    BulkAccountTaskCreate,
)

IST = ZoneInfo("Asia/Kolkata")


def task_to_dict(
    task: AccountTask,
    db: Session | None = None,
    users_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    # Check if task is overdue based on due date
    effective_status = task.computed_task_status

    acc_owner_id = task.account_owner_id
    if not acc_owner_id and task.account:
        acc_owner_id = task.account.account_owner_id

    acc_owner_name = task.account_owner
    if not acc_owner_name and task.account and task.account.owner:
        acc_owner_name = task.account.owner.full_name or task.account.owner.email

    assigned_id = task.assigned_to_id or acc_owner_id
    assigned_name = None
    if task.assigned_to:
        assigned_name = task.assigned_to.full_name or task.assigned_to.email
    elif task.account and task.account.owner:
        assigned_name = task.account.owner.full_name or task.account.owner.email

    created_by_name = None
    if task.created_by:
        created_by_name = task.created_by.full_name or task.created_by.email

    if not created_by_name and task.created_by_id:
        c_str = str(task.created_by_id)
        if users_map and c_str in users_map:
            created_by_name = users_map[c_str]
        elif db:
            try:
                u = db.query(User).filter(or_(User.id == int(task.created_by_id), User.zuid == c_str)).first()
                if u:
                    created_by_name = u.full_name or u.email
            except Exception:
                pass

    if not assigned_name and assigned_id:
        a_str = str(assigned_id)
        if users_map and a_str in users_map:
            assigned_name = users_map[a_str]
        elif db:
            try:
                u = db.query(User).filter(or_(User.id == int(assigned_id), User.zuid == a_str)).first()
                if u:
                    assigned_name = u.full_name or u.email
            except Exception:
                pass

    return {
        "id": str(task.id) if task.id is not None else None,
        "module_name": task.module_name or "Account",
        "account_id": str(task.account_id) if task.account_id is not None else None,
        "account_name": task.account_name or (task.account.account_name if task.account else None),
        "account_owner": acc_owner_name,
        "account_owner_id": str(acc_owner_id) if acc_owner_id is not None else None,
        "account_status": task.account_status,
        "account_stage": task.account_stage,
        "call_back_date_status": task.call_back_date_status,
        "task_type": task.task_type,
        "task_description": task.task_description,
        "task_assigned_date_time": task.task_assigned_date_time,
        "task_due_date_time": task.task_due_date_time,
        "task_status": effective_status,
        "assigned_to_id": str(assigned_id) if assigned_id is not None else None,
        "assigned_to_name": assigned_name,
        "created_by_id": str(task.created_by_id) if task.created_by_id is not None else None,
        "created_by_name": created_by_name,
        "modified_by_id": str(task.modified_by_id) if task.modified_by_id is not None else None,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def create_account_task(db: Session, task_in: AccountTaskCreate, current_user_id: int):
    acc_id_int = None
    try:
        acc_id_int = int(task_in.account_id)
    except Exception:
        pass

    account = (
        db.query(Account)
        .filter(or_(Account.id == task_in.account_id, Account.id == acc_id_int))
        .first()
    )
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with ID {task_in.account_id} not found",
        )

    task = AccountTask(
        company_id=1,
        module_name=task_in.module_name or "Account",
        account_id=account.id,
        account_owner_id=account.account_owner_id,
        task_type=task_in.task_type,
        task_description=task_in.task_description or "",
        task_assigned_date_time=task_in.task_assigned_date_time,
        task_due_date_time=task_in.task_due_date_time,
        task_status=task_in.task_status or "Unassigned",
        assigned_to_id=task_in.assigned_to_id,
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
        {
            "account_id": task.account_id,
            "task_type": task.task_type,
            "task_status": task.task_status,
        },
    )

    return task_to_dict(task, db=db)


def bulk_create_account_tasks(
    db: Session, bulk_in: BulkAccountTaskCreate, current_user_id: int
):
    if not bulk_in.account_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No account IDs provided for bulk creation",
        )

    int_account_ids = []
    for aid in bulk_in.account_ids:
        try:
            int_account_ids.append(int(aid))
        except Exception:
            pass

    created_tasks = []

    accounts = (
        db.query(Account)
        .filter(
            or_(Account.id.in_(bulk_in.account_ids), Account.id.in_(int_account_ids)),
            or_(Account.company_id == 1, Account.company_id.is_(None)),
        )
        .all()
    )
    account_map_int = {acc.id: acc for acc in accounts}
    account_map_str = {str(acc.id): acc for acc in accounts}

    assigned_dt = bulk_in.task_assigned_date_time

    for acc_id in bulk_in.account_ids:
        account = account_map_str.get(str(acc_id)) or account_map_int.get(acc_id)
        if not account:
            try:
                account = account_map_int.get(int(acc_id))
            except Exception:
                pass
        if not account:
            continue

        task = AccountTask(
            company_id=1,
            module_name="Account",
            account_id=account.id,
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
    account_id: int | None = None,
    task_status: str | None = None,
    task_type: str | None = None,
    call_back_status: str | None = None,
    search: str | None = None,
    assigned_to_id: int | None = None,
    account_owner_id: list[int] | None = None,
    # New Account Filters
    source_type: list[str] | None = None,
    account_stage: list[str] | None = None,
    business_status: list[str] | None = None,
    waba_interested: str | None = None,
    is_priority_account: str | None = None,
    # Advanced Call Back Filter Section
    cb_condition: str | None = None,
    cb_users: list[int] | None = None,
    cb_date_condition: str | None = None,
    cb_from_date: str | None = None,
    cb_to_date: str | None = None,
    assigned_date_condition: str | None = None,
    assigned_from_date: str | None = None,
    assigned_to_date: str | None = None,
    created_from_date: str | None = None,
    created_to_date: str | None = None,
    user_id: int | None = None,
    user_role: str | None = None,
):
    query = (
        db.query(AccountTask)
        .options(
            joinedload(AccountTask.account).joinedload(Account.owner),
            joinedload(AccountTask.assigned_to),
            joinedload(AccountTask.created_by),
        )
        .filter(or_(AccountTask.company_id == 1, AccountTask.company_id.is_(None)))
    )

    effective_cb_date = cb_date_condition or (
        call_back_status if call_back_status != "all" else None
    )
    effective_cb_cond = cb_condition or "Is"

    bypass_ids = getattr(MANAGERID, "BYPASS_USER_IDS", set())
    is_non_admin = bool(
        user_role
        and str(user_role).lower() not in ("super_admin", "admin")
        and (user_id is None or int(user_id) not in bypass_ids)
    )

    needs_account_join = bool(
        account_owner_id
        or source_type
        or account_stage
        or business_status
        or waba_interested
        or is_priority_account
        or effective_cb_cond
        or cb_users
        or effective_cb_date
        or cb_from_date
        or cb_to_date
        or search
        or is_non_admin
    )

    if needs_account_join:
        query = query.join(AccountTask.account)

    # Role-based visibility filtering
    if user_id is not None and user_role:
        uid = int(user_id)
        role = str(user_role).lower()
        if role in ("super_admin", "admin") or uid in bypass_ids:
            pass
        elif role == "manager":
            mgr_map = getattr(MANAGERID, "MANAGER_EXECUTIVES_MAP", {})
            if not mgr_map and callable(MANAGERID):
                try:
                    mgr_map = MANAGERID().MANAGER_EXECUTIVES_MAP
                except Exception:
                    pass
            allowed_ids = [uid] + [
                int(x) for x in mgr_map.get(uid, []) if str(x).isdigit()
            ]
            query = query.filter(
                or_(
                    Account.account_owner_id.in_(allowed_ids),
                    AccountTask.assigned_to_id.in_(allowed_ids),
                    AccountTask.created_by_id.in_(allowed_ids),
                )
            )
        else:
            query = query.filter(
                or_(
                    Account.account_owner_id == uid,
                    AccountTask.assigned_to_id == uid,
                    AccountTask.created_by_id == uid,
                )
            )

    if account_id:
        query = query.filter(AccountTask.account_id == account_id)
    if task_status and task_status.lower() != "all":
        if task_status == "Overdue":
            now_utc = datetime.now(UTC)
            query = query.filter(
                or_(
                    AccountTask.task_status == "Overdue",
                    and_(
                        AccountTask.task_due_date_time.isnot(None),
                        AccountTask.task_due_date_time < now_utc,
                        AccountTask.task_status.not_in(["Completed", "Verified"]),
                    ),
                )
            )
        else:
            query = query.filter(AccountTask.task_status == task_status)
    if task_type:
        query = query.filter(AccountTask.task_type == task_type)
    if assigned_to_id:
        query = query.filter(AccountTask.assigned_to_id == assigned_to_id)
    if account_owner_id:
        if isinstance(account_owner_id, (str, int)):
            raw_ids = [account_owner_id]
        elif isinstance(account_owner_id, list):
            raw_ids = account_owner_id
        else:
            raw_ids = []

        owner_ids = []
        for item in raw_ids:
            if isinstance(item, str) and "," in item:
                owner_ids.extend([int(x.strip()) for x in item.split(",") if x.strip().isdigit()])
            elif str(item).isdigit():
                owner_ids.append(int(item))

        if owner_ids:
            query = query.filter(
                or_(
                    Account.account_owner_id.in_(owner_ids),
                    AccountTask.assigned_to_id.in_(owner_ids),
                )
            )
    if search:
        query = query.filter(
            or_(
                AccountTask.task_description.ilike(f"%{search}%"),
                AccountTask.task_type.ilike(f"%{search}%"),
                Account.account_name.ilike(f"%{search}%"),
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
                Account.account_owner_id.in_(cb_users),
            )
        )

    if effective_cb_date:
        now_utc = datetime.now(UTC)
        now_ist = now_utc.astimezone(IST)
        today_start = datetime(
            now_ist.year, now_ist.month, now_ist.day, 0, 0, 0, tzinfo=IST
        )
        today_end = datetime(
            now_ist.year, now_ist.month, now_ist.day, 23, 59, 59, tzinfo=IST
        )

        if effective_cb_date == "Blank":
            cb_clauses.append(Account.call_back_date_time.is_(None))
        elif effective_cb_date == "Overdue":
            cb_clauses.append(
                and_(
                    Account.call_back_date_time.isnot(None),
                    Account.call_back_date_time < today_start,
                )
            )
        elif effective_cb_date == "Due Today":
            cb_clauses.append(
                Account.call_back_date_time.between(today_start, today_end)
            )
        elif effective_cb_date == "Due Tomorrow":
            tomorrow_start = today_start + timedelta(days=1)
            tomorrow_end = today_end + timedelta(days=1)
            cb_clauses.append(
                Account.call_back_date_time.between(tomorrow_start, tomorrow_end)
            )
        elif effective_cb_date == "Due This Week":
            weekday = today_start.weekday()
            start_of_week = today_start - timedelta(days=weekday)
            end_of_week = today_start + timedelta(
                days=(6 - weekday), hours=23, minutes=59, seconds=59
            )
            cb_clauses.append(
                Account.call_back_date_time.between(start_of_week, end_of_week)
            )
        elif effective_cb_date == "Due Next Week":
            weekday = today_start.weekday()
            start_of_next_week = today_start + timedelta(days=(7 - weekday))
            end_of_next_week = start_of_next_week + timedelta(
                days=6, hours=23, minutes=59, seconds=59
            )
            cb_clauses.append(
                Account.call_back_date_time.between(
                    start_of_next_week, end_of_next_week
                )
            )
        elif effective_cb_date == "Due Dates" and cb_from_date and cb_to_date:
            try:
                f_dt = datetime.strptime(cb_from_date, "%Y-%m-%d").replace(tzinfo=IST)
                t_dt = datetime.strptime(cb_to_date, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, tzinfo=IST
                )
                cb_clauses.append(Account.call_back_date_time.between(f_dt, t_dt))
            except Exception:
                pass

    if cb_clauses:
        combined_clause = and_(*cb_clauses)
        if effective_cb_cond == "Not":
            query = query.filter(not_(combined_clause))
        else:
            query = query.filter(combined_clause)

    # Assigned Date Filter Section (IST calculations)
    if assigned_from_date or assigned_to_date:
        try:
            if assigned_from_date and assigned_to_date:
                f_dt = datetime.strptime(assigned_from_date, "%Y-%m-%d").replace(tzinfo=IST)
                t_dt = datetime.strptime(assigned_to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=IST)
                query = query.filter(AccountTask.task_assigned_date_time.between(f_dt, t_dt))
            elif assigned_from_date:
                f_dt = datetime.strptime(assigned_from_date, "%Y-%m-%d").replace(tzinfo=IST)
                query = query.filter(AccountTask.task_assigned_date_time >= f_dt)
            elif assigned_to_date:
                t_dt = datetime.strptime(assigned_to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=IST)
                query = query.filter(AccountTask.task_assigned_date_time <= t_dt)
        except Exception:
            pass

    # Created Date Filter Section (IST calculations)
    if created_from_date or created_to_date:
        try:
            if created_from_date and created_to_date:
                f_dt = datetime.strptime(created_from_date, "%Y-%m-%d").replace(
                    tzinfo=IST
                )
                t_dt = datetime.strptime(created_to_date, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, tzinfo=IST
                )
                query = query.filter(AccountTask.created_at.between(f_dt, t_dt))
            elif created_from_date:
                f_dt = datetime.strptime(created_from_date, "%Y-%m-%d").replace(
                    tzinfo=IST
                )
                query = query.filter(AccountTask.created_at >= f_dt)
            elif created_to_date:
                t_dt = datetime.strptime(created_to_date, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, tzinfo=IST
                )
                query = query.filter(AccountTask.created_at <= t_dt)
        except Exception:
            pass

    total_records = query.count()
    total_pages = math.ceil(total_records / page_size) if page_size > 0 else 1

    offset = (page - 1) * page_size
    tasks = (
        query.order_by(desc(AccountTask.updated_at))
        .offset(offset)
        .limit(page_size)
        .all()
    )

    results = []
    now = datetime.now(UTC)

    all_users = db.query(User).all()
    users_map = {}
    for u in all_users:
        u_name = u.full_name or u.email
        if u.id:
            users_map[str(u.id)] = u_name
        if getattr(u, "zuid", None):
            users_map[str(u.zuid)] = u_name

    for task in tasks:
        if task.task_due_date_time and task.task_status not in [
            "Completed",
            "Verified",
        ]:
            due = task.task_due_date_time
            if due.tzinfo is None:
                due = due.replace(tzinfo=UTC)
            if due < now and task.task_status != "Overdue":
                task.task_status = "Overdue"
                db.add(task)
                db.commit()

        results.append(task_to_dict(task, db=db, users_map=users_map))

    return {
        "data": results,
        "page_info": {
            "page": page,
            "total_pages": total_pages,
            "total_records": total_records,
        },
    }


def check_task_access(task: AccountTask, user_id: int | None, user_role: str | None):
    if not user_id or not user_role:
        return
    uid = int(user_id)
    role = str(user_role).lower()
    bypass_ids = getattr(MANAGERID, "BYPASS_USER_IDS", set())
    if role in ("super_admin", "admin") or uid in bypass_ids:
        return

    allowed_ids = []
    if role == "manager":
        mgr_map = getattr(MANAGERID, "MANAGER_EXECUTIVES_MAP", {})
        if not mgr_map and callable(MANAGERID):
            try:
                mgr_map = MANAGERID().MANAGER_EXECUTIVES_MAP
            except Exception:
                pass
        allowed_ids = [uid] + [int(x) for x in mgr_map.get(uid, []) if str(x).isdigit()]
    else:
        allowed_ids = [uid]

    acc_owner_id = task.account.account_owner_id if task.account else None
    assigned_id = task.assigned_to_id
    created_id = task.created_by_id

    if (
        acc_owner_id not in allowed_ids
        and assigned_id not in allowed_ids
        and created_id not in allowed_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this account task",
        )


def get_account_task_by_id(
    db: Session,
    task_id: int,
    mongodb: Any | None = None,
    user_id: int | None = None,
    user_role: str | None = None,
):
    task = (
        db.query(AccountTask)
        .options(
            joinedload(AccountTask.account).joinedload(Account.owner),
            joinedload(AccountTask.assigned_to),
        )
        .filter(
            AccountTask.id == task_id,
            or_(AccountTask.company_id == 1, AccountTask.company_id.is_(None)),
        )
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account Task with ID {task_id} not found",
        )

    check_task_access(task, user_id, user_role)

    task_dict = task_to_dict(task, db=db)
    if mongodb is not None:
        try:
            notes = get_notes(
                id_list=[str(task_id)],
                notes_collection=mongodb["Notes"],
                module_name=[
                    "Account_Tasks",
                    "AccountTask",
                    "AccountTasks",
                    "Account Task",
                ],
            )
            task_dict["notes"] = notes
        except Exception:
            task_dict["notes"] = []
    else:
        task_dict["notes"] = []

    return task_dict


def update_account_task(
    db: Session,
    task_id: int,
    task_in: AccountTaskUpdate,
    current_user_id: int,
    user_role: str | None = None,
):
    task = (
        db.query(AccountTask)
        .options(joinedload(AccountTask.account))
        .filter(
            AccountTask.id == task_id,
            or_(AccountTask.company_id == 1, AccountTask.company_id.is_(None)),
        )
        .first()
    )
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account Task with ID {task_id} not found",
        )

    check_task_access(task, current_user_id, user_role)

    update_data = task_in.model_dump(exclude_unset=True)

    # Executive field update restriction: Executives can only mark tasks as completed
    role = str(user_role).lower() if user_role else ""
    bypass_ids = getattr(MANAGERID, "BYPASS_USER_IDS", set())
    if (
        role not in ("super_admin", "admin", "manager")
        and current_user_id not in bypass_ids
    ):
        non_status_changes = [k for k in update_data.keys() if k != "task_status"]
        if non_status_changes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account Owners are only permitted to update task status.",
            )

    new_requested_status = update_data.get("task_status")
    if new_requested_status:
        user_ids = {str(current_user_id)}
        try:
            u = db.query(User).filter(or_(User.id == current_user_id, User.zuid == str(current_user_id))).first()
            if u:
                user_ids.add(str(u.id))
                if getattr(u, "zuid", None):
                    user_ids.add(str(u.zuid))
        except Exception:
            pass

        allowed_owner_ids = set()
        if task.account_owner_id:
            allowed_owner_ids.add(str(task.account_owner_id))
        if task.account and task.account.account_owner_id:
            allowed_owner_ids.add(str(task.account.account_owner_id))
        if task.assigned_to_id:
            allowed_owner_ids.add(str(task.assigned_to_id))

        is_owner = bool(user_ids.intersection(allowed_owner_ids))
        if is_owner and new_requested_status not in ("Pending", "In Progress", "Completed", "Verified"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account Owners can only set task status to Pending, In Progress, Completed, or Verified.",
            )

    old_status = task.task_status
    for field, val in update_data.items():
        setattr(task, field, val)
    new_status = task.task_status

    if new_status != "Unassigned" and not task.assigned_to_id and task.account:
        task.assigned_to_id = task.account.account_owner_id

    task.modified_by_id = current_user_id
    task.updated_at = datetime.now(UTC)

    db.add(task)
    db.commit()
    db.refresh(task)

    if old_status == "Unassigned" and new_status != "Unassigned":
        from src.controllers.Background_threads import BackgroundThreadPool
        from src.controllers.mail import notify_task_unassigned_status_change

        BackgroundThreadPool.execute_task(
            notify_task_unassigned_status_change, task.id, old_status, new_status
        )

    log_action(
        db,
        current_user_id,
        user_role or "USER",
        "UPDATED",
        "AccountTask",
        task.id,
        update_data,
    )

    return task_to_dict(task, db=db)


def bulk_update_task_status(
    db: Session,
    task_ids: list[int],
    new_status: str,
    current_user_id: int | None,
    current_role: str | None = None,
):
    if not task_ids:
        return {"message": "No tasks provided", "updated_count": 0}

    tasks = (
        db.query(AccountTask)
        .options(joinedload(AccountTask.account))
        .filter(
            AccountTask.id.in_(task_ids),
            or_(AccountTask.company_id == 1, AccountTask.company_id.is_(None)),
        )
        .all()
    )

    if not tasks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching account tasks found",
        )

    # Permission check: Mass update of task status is available ONLY to the task creator
    role = str(current_role).lower() if current_role else ""
    bypass_ids = getattr(MANAGERID, "BYPASS_USER_IDS", set())
    if role not in ("super_admin", "admin") and (
        current_user_id not in bypass_ids if current_user_id else True
    ):
        unauthorized_tasks = [t.id for t in tasks if t.created_by_id != current_user_id]
        if unauthorized_tasks:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Mass update task status is allowed only for tasks created by you. (Unauthorized for task IDs: {unauthorized_tasks})",
            )

    # Permission check for marking tasks as completed
    if new_status == "Completed":
        role = str(current_role).lower() if current_role else ""
        if role not in ("super_admin", "admin", "manager"):
            user_ids = {str(current_user_id)}
            try:
                u = db.query(User).filter(or_(User.id == current_user_id, User.zuid == str(current_user_id))).first()
                if u:
                    user_ids.add(str(u.id))
                    if getattr(u, "zuid", None):
                        user_ids.add(str(u.zuid))
            except Exception:
                pass

            unauthorized_completion = []
            for t in tasks:
                t_allowed = set()
                if t.account_owner_id:
                    t_allowed.add(str(t.account_owner_id))
                if t.account and t.account.account_owner_id:
                    t_allowed.add(str(t.account.account_owner_id))
                if t.assigned_to_id:
                    t_allowed.add(str(t.assigned_to_id))
                if t.created_by_id:
                    t_allowed.add(str(t.created_by_id))
                if not user_ids.intersection(t_allowed):
                    unauthorized_completion.append(t.id)

            if unauthorized_completion:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Only the Account Owner, Assigned User, or Manager/Admin can mark tasks as completed. (Unauthorized for task IDs: {unauthorized_completion})",
                )

    updated_count = 0
    from src.controllers.Background_threads import BackgroundThreadPool
    from src.controllers.mail import notify_task_unassigned_status_change

    for task in tasks:
        old_status = task.task_status
        if old_status != new_status:
            task.task_status = new_status
            task.modified_by_id = current_user_id
            task.updated_at = datetime.now(UTC)
            db.add(task)
            updated_count += 1

            if old_status == "Unassigned" and new_status != "Unassigned":
                BackgroundThreadPool.execute_task(
                    notify_task_unassigned_status_change,
                    task.id,
                    old_status,
                    new_status,
                )

    db.commit()

    if current_user_id:
        log_action(
            db,
            current_user_id,
            current_role or "USER",
            "BULK_UPDATED_STATUS",
            "AccountTask",
            0,
            {
                "task_ids": task_ids,
                "new_status": new_status,
                "updated_count": updated_count,
            },
        )

    return {
        "message": f"Successfully updated status to '{new_status}' for {updated_count} task(s)",
        "updated_count": updated_count,
    }


def delete_account_task(
    db: Session,
    task_id: int,
    current_user_id: int,
    user_role: str | None = None,
):
    task = (
        db.query(AccountTask)
        .options(joinedload(AccountTask.account))
        .filter(
            AccountTask.id == task_id,
            or_(AccountTask.company_id == 1, AccountTask.company_id.is_(None)),
        )
        .first()
    )
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account Task with ID {task_id} not found",
        )

    check_task_access(task, current_user_id, user_role)

    db.delete(task)
    db.commit()

    log_action(
        db,
        current_user_id,
        user_role or "USER",
        "DELETED",
        "AccountTask",
        task_id,
        {},
    )
    return {"message": "Account Task deleted successfully"}
