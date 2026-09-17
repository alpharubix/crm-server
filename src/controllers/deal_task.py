import math
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import and_, not_, or_
from sqlalchemy.orm import Session, joinedload

from src.controllers.audit_log import log_action
from src.controllers.auth import MANAGERID
from src.controllers.notes import get_notes
from src.models.account import Account
from src.models.deal import Deal
from src.models.deal_task import DealTask
from src.models.user import User
from src.schemas.deal_task import (
    BulkDealTaskCreate,
    DealTaskCreate,
    DealTaskUpdate,
)

IST = ZoneInfo("Asia/Kolkata")


def task_to_dict(
    task: DealTask,
    db: Session | None = None,
    users_map: dict[str, str] | None = None,
) -> dict[str, Any]:
    effective_status = task.computed_task_status

    d_owner_id = task.deal_owner_id
    if not d_owner_id and task.deal:
        d_owner_id = task.deal.deal_owner_id

    d_owner_name = task.deal_owner
    if not d_owner_name and task.deal and task.deal.owner:
        d_owner_name = task.deal.owner.full_name or task.deal.owner.email

    assigned_id = task.assigned_to_id or d_owner_id
    assigned_name = None
    if task.assigned_to:
        assigned_name = task.assigned_to.full_name or task.assigned_to.email
    elif task.deal and task.deal.owner:
        assigned_name = task.deal.owner.full_name or task.deal.owner.email

    created_by_name = None
    if task.created_by:
        created_by_name = task.created_by.full_name or task.created_by.email

    if not created_by_name and task.created_by_id:
        c_str = str(task.created_by_id)
        if users_map and c_str in users_map:
            created_by_name = users_map[c_str]
        elif db:
            try:
                c_int = int(c_str) if c_str.isdigit() else None
                u = (
                    db.query(User)
                    .filter(or_(User.id == c_int, User.zuid == c_str))
                    .first()
                )
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
                a_int = int(a_str) if a_str.isdigit() else None
                u = (
                    db.query(User)
                    .filter(or_(User.id == a_int, User.zuid == a_str))
                    .first()
                )
                if u:
                    assigned_name = u.full_name or u.email
            except Exception:
                pass

    acc_owner_id = getattr(task, "account_owner_id", None)
    if not acc_owner_id and task.deal and task.deal.account:
        acc_owner_id = task.deal.account.account_owner_id

    acc_owner_name = getattr(task, "account_owner", None)
    if not acc_owner_name and task.deal and task.deal.account and task.deal.account.owner:
        acc_owner_name = (
            task.deal.account.owner.full_name or task.deal.account.owner.email
        )

    if not acc_owner_name and acc_owner_id:
        acc_str = str(acc_owner_id)
        if users_map and acc_str in users_map:
            acc_owner_name = users_map[acc_str]
        elif db:
            try:
                acc_int = int(acc_str) if acc_str.isdigit() else None
                u = (
                    db.query(User)
                    .filter(or_(User.id == acc_int, User.zuid == acc_str))
                    .first()
                )
                if u:
                    acc_owner_name = u.full_name or u.email
            except Exception:
                pass

    call_back_dt = None
    if task.deal and getattr(task.deal, "deal_call_back_datetime", None):
        cb = task.deal.deal_call_back_datetime
        call_back_dt = cb.isoformat() if hasattr(cb, "isoformat") else str(cb)

    completed_at_dt = None
    if getattr(task, "completed_at", None):
        ca = task.completed_at
        completed_at_dt = ca.isoformat() if hasattr(ca, "isoformat") else str(ca)

    return {
        "id": str(task.id) if task.id is not None else None,
        "module_name": task.module_name or "Deal",
        "deal_id": str(task.deal_id) if task.deal_id is not None else None,
        "deal_name": task.deal_name or (task.deal.deal_name if task.deal else None),
        "account_id": str(task.account_id)
        if task.account_id is not None
        else (
            str(task.deal.account_id) if task.deal and task.deal.account_id else None
        ),
        "account_name": task.account_name
        or (task.deal.account_name if task.deal else None),
        "account_owner": acc_owner_name,
        "account_owner_id": str(acc_owner_id) if acc_owner_id is not None else None,
        "deal_owner": d_owner_name,
        "deal_owner_id": str(d_owner_id) if d_owner_id is not None else None,
        "deal_status": task.deal_status
        or (task.deal.deal_status if task.deal else None),
        "deal_stage": task.deal_stage or (task.deal.deal_stage if task.deal else None),
        "loan_type": task.loan_type or (task.deal.loan_type if task.deal else None),
        "lender_name": task.lender_name
        or (task.deal.lender_name if task.deal else None),
        "call_back_date_status": task.call_back_date_status,
        "call_back_date_time": call_back_dt,
        "deal_assigned_date_time": None,
        "task_type": task.task_type,
        "task_description": task.task_description,
        "task_assigned_date_time": task.task_assigned_date_time,
        "task_due_date_time": task.task_due_date_time,
        "task_status": effective_status,
        "target_deal_status": getattr(task, "target_deal_status", None),
        "completed_at": completed_at_dt,
        "assigned_to_id": str(assigned_id) if assigned_id is not None else None,
        "assigned_to_name": assigned_name,
        "created_by_id": str(task.created_by_id)
        if task.created_by_id is not None
        else None,
        "created_by_name": created_by_name,
        "modified_by_id": str(task.modified_by_id)
        if task.modified_by_id is not None
        else None,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


FALLBACK_COMPLETION_STATUSES = {
    "on hold",
    "not interested",
    "location unserviceable",
    "loc unservice",
    "business closed",
    "rejected",
    "closed",
    "disbursed",
}


def is_fallback_completion_status(status_str: str | None) -> bool:
    if not status_str:
        return False
    s = str(status_str).strip().lower()
    if s in FALLBACK_COMPLETION_STATUSES:
        return True
    if any(
        k in s
        for k in (
            "on hold",
            "not interested",
            "unservice",
            "business closed",
            "reject",
            "close",
            "disburs",
        )
    ):
        return True
    return False


def validate_target_fields_for_completion(
    task: DealTask,
    target_status: str | None = None,
):
    deal = task.deal
    if not deal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot complete task: Linked deal not found.",
        )

    d_status = (deal.deal_status or "").strip()
    norm_d_status = d_status.lower()
    is_fallback = is_fallback_completion_status(norm_d_status)

    if target_status and str(target_status).strip():
        expected_status = str(target_status).strip()
        norm_expected = expected_status.lower()
        if norm_expected not in ("n/a", "na"):
            is_target_matched = norm_d_status == expected_status.lower()

            if not (is_target_matched or is_fallback):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Cannot complete task: Deal status ('{d_status or 'Blank'}') "
                        f"does not match target deal status ('{expected_status}')."
                    ),
                )


def create_deal_task(db: Session, task_in: DealTaskCreate, current_user_id: int):
    d_id_int = None
    try:
        d_id_int = int(task_in.deal_id)
    except Exception:
        pass

    deal = (
        db.query(Deal)
        .filter(or_(Deal.id == task_in.deal_id, Deal.id == d_id_int))
        .first()
    )
    if not deal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deal with ID {task_in.deal_id} not found",
        )

    init_status = task_in.task_status or "Unassigned"
    assigned_dt = datetime.now(UTC) if init_status == "Assigned" else None

    task = DealTask(
        company_id=1,
        module_name=task_in.module_name or "Deal",
        deal_id=deal.id,
        task_type=task_in.task_type,
        task_description=task_in.task_description or "",
        task_assigned_date_time=assigned_dt,
        task_due_date_time=task_in.task_due_date_time,
        task_status=init_status,
        target_deal_status=task_in.target_deal_status,
        assigned_to_id=task_in.assigned_to_id or deal.deal_owner_id,
        created_by_id=current_user_id,
        modified_by_id=current_user_id,
    )
    task.deal = deal
    if task.task_status == "Completed":
        validate_target_fields_for_completion(task, task.target_deal_status)
        task.completed_at = datetime.now(UTC)

    db.add(task)
    db.commit()
    db.refresh(task)

    log_action(
        db,
        current_user_id,
        "USER",
        "CREATED",
        "DealTask",
        task.id,
        {
            "deal_id": task.deal_id,
            "task_type": task.task_type,
            "task_status": task.task_status,
        },
    )

    return task_to_dict(task, db=db)


def bulk_create_deal_tasks(
    db: Session, bulk_in: BulkDealTaskCreate, current_user_id: int
):
    if not bulk_in.deal_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No deal IDs provided for bulk creation",
        )

    int_deal_ids = []
    for did in bulk_in.deal_ids:
        try:
            int_deal_ids.append(int(did))
        except Exception:
            pass

    created_tasks = []

    deals = (
        db.query(Deal)
        .filter(
            or_(Deal.id.in_(bulk_in.deal_ids), Deal.id.in_(int_deal_ids)),
            or_(Deal.company_id == 1, Deal.company_id.is_(None)),
        )
        .all()
    )
    deal_map_int = {d.id: d for d in deals}
    deal_map_str = {str(d.id): d for d in deals}

    bulk_status = bulk_in.task_status or "Unassigned"
    assigned_dt = datetime.now(UTC) if bulk_status == "Assigned" else None

    for did in bulk_in.deal_ids:
        deal = deal_map_str.get(str(did)) or deal_map_int.get(did)
        if not deal:
            try:
                deal = deal_map_int.get(int(did))
            except Exception:
                pass
        if not deal:
            continue

        task = DealTask(
            company_id=1,
            module_name="Deal",
            deal_id=deal.id,
            task_type="Update Record",
            task_description=bulk_in.task_description or "",
            task_assigned_date_time=assigned_dt,
            task_due_date_time=bulk_in.task_due_date_time,
            task_status=bulk_status,
            assigned_to_id=deal.deal_owner_id,
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
        "DealTask",
        0,
        {
            "deal_ids": bulk_in.deal_ids,
            "tasks_count": len(created_tasks),
        },
    )

    return {
        "message": f"Successfully created {len(created_tasks)} task(s) for {len(deals)} deal(s)",
        "tasks_count": len(created_tasks),
    }


def check_deal_task_access(task: DealTask, user_id: int | None, user_role: str | None):
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

    d_owner_id = task.deal.deal_owner_id if task.deal else None
    assigned_id = task.assigned_to_id
    created_id = task.created_by_id

    if (
        d_owner_id not in allowed_ids
        and assigned_id not in allowed_ids
        and created_id not in allowed_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this deal task",
        )


def get_deal_tasks(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    deal_id: int | None = None,
    account_id: int | None = None,
    account_owner_id: str | None = None,
    task_status: str | None = None,
    task_type: str | None = None,
    call_back_status: str | None = None,
    search: str | None = None,
    assigned_to_id: int | None = None,
    deal_owner_id: list[int] | None = None,
    loan_type: list[str] | None = None,
    deal_stage: list[str] | None = None,
    deal_status: list[str] | None = None,
    lender_name: list[str] | None = None,
    # Date condition filters
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
    mongodb: Any | None = None,
):
    query = (
        db.query(DealTask)
        .options(
            joinedload(DealTask.deal).joinedload(Deal.owner),
            joinedload(DealTask.deal).joinedload(Deal.account).joinedload(Account.owner),
            joinedload(DealTask.assigned_to),
            joinedload(DealTask.created_by),
        )
        .filter(or_(DealTask.company_id == 1, DealTask.company_id.is_(None)))
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

    needs_deal_join = bool(
        account_id
        or deal_owner_id
        or loan_type
        or deal_stage
        or deal_status
        or lender_name
        or effective_cb_cond
        or cb_users
        or effective_cb_date
        or cb_from_date
        or cb_to_date
        or search
        or is_non_admin
    )

    if needs_deal_join:
        query = query.join(DealTask.deal)

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
                    Deal.deal_owner_id.in_(allowed_ids),
                    DealTask.assigned_to_id.in_(allowed_ids),
                    DealTask.created_by_id.in_(allowed_ids),
                )
            )
        else:
            query = query.filter(
                or_(
                    Deal.deal_owner_id == uid,
                    DealTask.assigned_to_id == uid,
                    DealTask.created_by_id == uid,
                )
            )

    if deal_id:
        query = query.filter(DealTask.deal_id == deal_id)
    if account_id:
        query = query.filter(Deal.account_id == account_id)

    if task_status and task_status.lower() != "all":
        if task_status == "Overdue":
            now_utc = datetime.now(UTC)
            query = query.filter(
                or_(
                    DealTask.task_status == "Overdue",
                    and_(
                        DealTask.task_due_date_time.isnot(None),
                        DealTask.task_due_date_time < now_utc,
                        DealTask.task_status.not_in(["Completed", "Verified"]),
                    ),
                )
            )
        else:
            query = query.filter(DealTask.task_status == task_status)

    if task_type:
        query = query.filter(DealTask.task_type == task_type)
    if assigned_to_id:
        query = query.filter(DealTask.assigned_to_id == assigned_to_id)

    if deal_owner_id:
        if isinstance(deal_owner_id, (str, int)):
            raw_ids = [deal_owner_id]
        elif isinstance(deal_owner_id, list):
            raw_ids = deal_owner_id
        else:
            raw_ids = []

        owner_ids = []
        for item in raw_ids:
            if isinstance(item, str) and "," in item:
                owner_ids.extend(
                    [int(x.strip()) for x in item.split(",") if x.strip().isdigit()]
                )
            elif str(item).isdigit():
                owner_ids.append(int(item))

        if owner_ids:
            query = query.filter(
                or_(
                    Deal.deal_owner_id.in_(owner_ids),
                    DealTask.assigned_to_id.in_(owner_ids),
                )
            )

    if search:
        query = query.filter(
            or_(
                DealTask.task_description.ilike(f"%{search}%"),
                DealTask.task_type.ilike(f"%{search}%"),
                Deal.deal_name.ilike(f"%{search}%"),
                Deal.account_name.ilike(f"%{search}%"),
                Deal.lender_name.ilike(f"%{search}%"),
            )
        )

    if loan_type:
        ltypes = loan_type if isinstance(loan_type, list) else [loan_type]
        query = query.filter(or_(*[Deal.loan_type.ilike(f"%{lt}%") for lt in ltypes]))

    if deal_stage:
        dstages = deal_stage if isinstance(deal_stage, list) else [deal_stage]
        query = query.filter(or_(*[Deal.deal_stage.ilike(f"%{ds}%") for ds in dstages]))

    if deal_status:
        dstatuses = deal_status if isinstance(deal_status, list) else [deal_status]
        query = query.filter(
            or_(*[Deal.deal_status.ilike(f"%{ds}%") for ds in dstatuses])
        )

    if lender_name:
        lnames = lender_name if isinstance(lender_name, list) else [lender_name]
        query = query.filter(or_(*[Deal.lender_name.ilike(f"%{ln}%") for ln in lnames]))

    # Advanced callback date filtering
    if effective_cb_date:
        now_utc = datetime.now(UTC)
        now_ist = now_utc.astimezone(IST)
        today_start_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end_ist = today_start_ist + timedelta(days=1)
        start_of_this_week = today_start_ist - timedelta(days=now_ist.weekday())
        end_of_this_week = start_of_this_week + timedelta(days=7)
        start_of_next_week = end_of_this_week
        end_of_next_week = start_of_next_week + timedelta(days=7)

        if effective_cb_date == "Due Today":
            date_filter = Deal.deal_call_back_datetime.between(
                today_start_ist, today_end_ist
            )
        elif effective_cb_date == "Due Tomorrow":
            date_filter = Deal.deal_call_back_datetime.between(
                today_end_ist, today_end_ist + timedelta(days=1)
            )
        elif effective_cb_date == "Due This Week":
            date_filter = Deal.deal_call_back_datetime.between(
                start_of_this_week, end_of_this_week
            )
        elif effective_cb_date == "Due Next Week":
            date_filter = Deal.deal_call_back_datetime.between(
                start_of_next_week, end_of_next_week
            )
        elif effective_cb_date == "Overdue":
            date_filter = and_(
                Deal.deal_call_back_datetime.isnot(None),
                Deal.deal_call_back_datetime < today_start_ist,
            )
        elif effective_cb_date == "Blank":
            date_filter = Deal.deal_call_back_datetime.is_(None)
        elif effective_cb_date == "Due Dates":
            if cb_from_date and cb_to_date:
                f_dt = datetime.fromisoformat(cb_from_date)
                t_dt = datetime.fromisoformat(cb_to_date)
                date_filter = Deal.deal_call_back_datetime.between(f_dt, t_dt)
            elif cb_from_date:
                f_dt = datetime.fromisoformat(cb_from_date)
                date_filter = Deal.deal_call_back_datetime >= f_dt
            elif cb_to_date:
                t_dt = datetime.fromisoformat(cb_to_date)
                date_filter = Deal.deal_call_back_datetime <= t_dt
            else:
                date_filter = Deal.deal_call_back_datetime.isnot(None)
        else:
            date_filter = None

        if date_filter is not None:
            if effective_cb_cond == "Is Not":
                query = query.filter(not_(date_filter))
            else:
                query = query.filter(date_filter)

    if assigned_date_condition:
        if assigned_from_date and assigned_to_date:
            f_dt = datetime.fromisoformat(assigned_from_date)
            t_dt = datetime.fromisoformat(assigned_to_date)
            cond = DealTask.task_assigned_date_time.between(f_dt, t_dt)
        elif assigned_from_date:
            f_dt = datetime.fromisoformat(assigned_from_date)
            cond = DealTask.task_assigned_date_time >= f_dt
        elif assigned_to_date:
            t_dt = datetime.fromisoformat(assigned_to_date)
            cond = DealTask.task_assigned_date_time <= t_dt
        else:
            cond = None

        if cond is not None:
            if assigned_date_condition == "Is Not":
                query = query.filter(not_(cond))
            else:
                query = query.filter(cond)

    if created_from_date and created_to_date:
        f_dt = datetime.fromisoformat(created_from_date)
        t_dt = datetime.fromisoformat(created_to_date)
        query = query.filter(DealTask.created_at.between(f_dt, t_dt))
    elif created_from_date:
        f_dt = datetime.fromisoformat(created_from_date)
        query = query.filter(DealTask.created_at >= f_dt)
    elif created_to_date:
        t_dt = datetime.fromisoformat(created_to_date)
        query = query.filter(DealTask.created_at <= t_dt)

    # Sort: pending/overdue first, earliest due date first
    total_records = query.count()
    total_pages = math.ceil(total_records / page_size) if total_records > 0 else 1
    offset = (page - 1) * page_size

    tasks = (
        query.order_by(
            DealTask.task_due_date_time.asc().nullslast(),
            DealTask.created_at.desc(),
        )
        .offset(offset)
        .limit(page_size)
        .all()
    )

    all_user_ids = set()
    for task in tasks:
        if task.created_by_id:
            all_user_ids.add(task.created_by_id)
        if task.assigned_to_id:
            all_user_ids.add(task.assigned_to_id)
        if task.deal_owner_id:
            all_user_ids.add(task.deal_owner_id)
        if getattr(task, "account_owner_id", None):
            all_user_ids.add(task.account_owner_id)

    users_map = {}
    if all_user_ids:
        try:
            int_uids = [int(x) for x in all_user_ids if str(x).isdigit()]
            str_uids = [str(x) for x in all_user_ids]
            users = (
                db.query(User)
                .filter(or_(User.id.in_(int_uids), User.zuid.in_(str_uids)))
                .all()
            )
            for u in users:
                name = u.full_name or u.email
                users_map[str(u.id)] = name
                if getattr(u, "zuid", None):
                    users_map[str(u.zuid)] = name
        except Exception:
            pass

    now_utc = datetime.now(UTC)
    results = []
    for task in tasks:
        # Check overdue status update
        if (
            task.task_status not in ["Completed", "Verified", "Overdue"]
            and task.task_due_date_time
        ):
            due = task.task_due_date_time
            if due.tzinfo is None:
                due = due.replace(tzinfo=UTC)
            if due < now_utc and task.task_status != "Overdue":
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


def get_deal_task_by_id(
    db: Session,
    task_id: str | int,
    mongodb: Any | None = None,
    user_id: str | int | None = None,
    user_role: str | None = None,
):
    t_int = int(task_id) if str(task_id).isdigit() else None
    task = (
        db.query(DealTask)
        .options(
            joinedload(DealTask.deal).joinedload(Deal.owner),
            joinedload(DealTask.deal).joinedload(Deal.account).joinedload(Account.owner),
            joinedload(DealTask.assigned_to),
        )
        .filter(
            or_(DealTask.id == task_id, DealTask.id == t_int),
            or_(DealTask.company_id == 1, DealTask.company_id.is_(None)),
        )
        .first()
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deal Task with ID {task_id} not found",
        )

    check_deal_task_access(task, int(user_id) if user_id else None, user_role)

    task_dict = task_to_dict(task, db=db)
    if mongodb is not None:
        try:
            notes = get_notes(
                id_list=[str(task_id)],
                notes_collection=mongodb["Notes"],
                module_name=[
                    "Deal_Tasks",
                    "DealTask",
                    "DealTasks",
                    "Deal Task",
                ],
            )
            task_dict["notes"] = notes
        except Exception:
            task_dict["notes"] = []
    else:
        task_dict["notes"] = []

    return task_dict


def update_deal_task(
    db: Session,
    task_id: str | int,
    task_in: DealTaskUpdate,
    current_user_id: str | int,
    user_role: str | None = None,
):
    t_int = int(task_id) if str(task_id).isdigit() else None
    task = (
        db.query(DealTask)
        .options(joinedload(DealTask.deal))
        .filter(
            or_(DealTask.id == task_id, DealTask.id == t_int),
            or_(DealTask.company_id == 1, DealTask.company_id.is_(None)),
        )
        .first()
    )
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Deal Task with ID {task_id} not found",
        )

    check_deal_task_access(task, int(current_user_id), user_role)

    update_data = task_in.model_dump(exclude_unset=True)

    # Immutability check: completed tasks cannot have status changed
    if task.task_status == "Completed":
        requested_status = update_data.get("task_status")
        if requested_status and requested_status != "Completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This task is already Completed. Completed task status cannot be changed.",
            )

    # Executive field update restriction: Executives can only update task status / completion
    role = str(user_role).lower() if user_role else ""
    bypass_ids = getattr(MANAGERID, "BYPASS_USER_IDS", set())
    bypass_str_set = {str(b) for b in bypass_ids}
    curr_user_str = str(current_user_id) if current_user_id is not None else ""
    curr_user_int = int(current_user_id) if curr_user_str.isdigit() else None

    if (
        role not in ("super_admin", "admin", "manager")
        and curr_user_str not in bypass_str_set
        and (curr_user_int is None or curr_user_int not in bypass_ids)
    ):
        allowed_exec_keys = {
            "task_status",
            "target_deal_status",
            "completed_at",
        }
        non_status_changes = [
            k for k in update_data.keys() if k not in allowed_exec_keys
        ]
        if non_status_changes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Deal Owners are only permitted to update task status.",
            )

    new_requested_status = update_data.get("task_status")
    if new_requested_status:
        user_ids = {curr_user_str}
        if curr_user_int is not None:
            user_ids.add(str(curr_user_int))
        try:
            u_filter = [User.zuid == curr_user_str]
            if curr_user_int is not None:
                u_filter.append(User.id == curr_user_int)
            u = db.query(User).filter(or_(*u_filter)).first()
            if u:
                user_ids.add(str(u.id))
                if getattr(u, "zuid", None):
                    user_ids.add(str(u.zuid))
        except Exception:
            pass

        allowed_owner_ids = set()
        if task.deal_owner_id:
            allowed_owner_ids.add(str(task.deal_owner_id))
        if task.deal and task.deal.deal_owner_id:
            allowed_owner_ids.add(str(task.deal.deal_owner_id))
        if task.assigned_to_id:
            allowed_owner_ids.add(str(task.assigned_to_id))

        is_owner = bool(user_ids.intersection(allowed_owner_ids))
        if (
            not is_owner
            and role not in ("super_admin", "admin", "manager")
            and curr_user_str not in bypass_str_set
            and (curr_user_int is None or curr_user_int not in bypass_ids)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the Task Owner, Deal Owner, or Manager/Admin can update task status.",
            )
        if is_owner and new_requested_status not in (
            "Pending",
            "In Progress",
            "Completed",
            "Verified",
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Task/Deal Owners can only set task status to Pending, In Progress, Completed, or Verified.",
            )

        if task.task_status != "Unassigned" and new_requested_status == "Unassigned":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot unassign a task once it has been assigned.",
            )
        if (
            task.task_status not in ("Unassigned", "Assigned")
            and new_requested_status == "Assigned"
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot revert task back to Assigned once it has progressed.",
            )

    old_status = task.task_status
    if new_requested_status == "Completed" and old_status != "Completed":
        target_st = (
            update_data["target_deal_status"]
            if "target_deal_status" in update_data
            else task.target_deal_status
        )
        validate_target_fields_for_completion(task, target_st)
        update_data["completed_at"] = datetime.now(UTC)

    # Assigned date handling:
    # Assigned date cannot be modified by anyone.
    # If status is not set to 'Assigned', date must be empty (None).
    # If status is set to 'Assigned', auto-set to current UTC time if not already set.
    update_data.pop("task_assigned_date_time", None)
    effective_status = update_data.get("task_status", task.task_status)
    if effective_status == "Assigned":
        if not task.task_assigned_date_time:
            task.task_assigned_date_time = datetime.now(UTC)
    else:
        task.task_assigned_date_time = None

    for field, value in update_data.items():
        setattr(task, field, value)

    task.modified_by_id = (
        int(current_user_id) if curr_user_int is not None else task.modified_by_id
    )
    task.updated_at = datetime.now(UTC)

    db.commit()
    db.refresh(task)

    # Email notification when status moves from Unassigned to another status
    if (
        old_status == "Unassigned"
        and new_requested_status
        and new_requested_status != "Unassigned"
    ):
        try:
            from src.controllers.Background_threads import BackgroundThreadPool
            from src.controllers.mail import notify_deal_task_unassigned_status_change

            BackgroundThreadPool.execute_task(
                notify_deal_task_unassigned_status_change,
                task.id,
                old_status,
                new_requested_status,
            )
        except Exception as e:
            print(f"Failed to dispatch deal task notification: {e}")

    log_action(
        db,
        int(current_user_id) if curr_user_int is not None else 0,
        user_role or "USER",
        "UPDATED",
        "DealTask",
        task.id,
        update_data,
    )

    return task_to_dict(task, db=db)


def bulk_update_deal_task_status(
    db: Session,
    task_ids: list[str | int],
    new_status: str,
    current_user_id: int | None,
    current_role: str | None = None,
):
    if not task_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No task IDs provided for bulk status update",
        )

    int_ids = []
    for tid in task_ids:
        try:
            int_ids.append(int(tid))
        except Exception:
            pass

    tasks = (
        db.query(DealTask)
        .options(joinedload(DealTask.deal))
        .filter(
            or_(DealTask.id.in_(task_ids), DealTask.id.in_(int_ids)),
            or_(DealTask.company_id == 1, DealTask.company_id.is_(None)),
        )
        .all()
    )

    if not tasks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No matching deal tasks found for the provided IDs",
        )

    role = str(current_role).lower() if current_role else ""
    bypass_ids = getattr(MANAGERID, "BYPASS_USER_IDS", set())
    bypass_str_set = {str(b) for b in bypass_ids}
    curr_user_str = str(current_user_id) if current_user_id is not None else ""
    curr_user_int = int(current_user_id) if curr_user_str.isdigit() else None

    if (
        role not in ("super_admin", "admin", "manager")
        and curr_user_str not in bypass_str_set
        and (curr_user_int is None or curr_user_int not in bypass_ids)
    ):
        if new_status == "Completed":
            user_ids = {curr_user_str}
            if curr_user_int is not None:
                user_ids.add(str(curr_user_int))
            try:
                u_filter = [User.zuid == curr_user_str]
                if curr_user_int is not None:
                    u_filter.append(User.id == curr_user_int)
                u = db.query(User).filter(or_(*u_filter)).first()
                if u:
                    user_ids.add(str(u.id))
                    if getattr(u, "zuid", None):
                        user_ids.add(str(u.zuid))
            except Exception:
                pass

            unauthorized_completion = []
            for t in tasks:
                t_allowed = set()
                if t.deal_owner_id:
                    t_allowed.add(str(t.deal_owner_id))
                if t.deal and t.deal.deal_owner_id:
                    t_allowed.add(str(t.deal.deal_owner_id))
                if t.assigned_to_id:
                    t_allowed.add(str(t.assigned_to_id))
                if t.created_by_id:
                    t_allowed.add(str(t.created_by_id))
                if not user_ids.intersection(t_allowed):
                    unauthorized_completion.append(t.id)

            if unauthorized_completion:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Only the Deal Owner, Assigned User, or Manager/Admin can mark tasks as completed. (Unauthorized for task IDs: {unauthorized_completion})",
                )

    # Check immutability for already completed tasks
    if new_status != "Completed":
        already_completed = [t.id for t in tasks if t.task_status == "Completed"]
        if already_completed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Task status cannot be changed for already completed tasks (Task IDs: {already_completed}).",
            )

    updated_count = 0
    now_completion = datetime.now(UTC)

    from src.controllers.Background_threads import BackgroundThreadPool
    from src.controllers.mail import notify_deal_task_unassigned_status_change

    for task in tasks:
        old_status = task.task_status
        if old_status != new_status:
            if new_status == "Completed":
                validate_target_fields_for_completion(task, task.target_deal_status)
                task.completed_at = now_completion

            task.task_status = new_status
            if current_user_id:
                task.modified_by_id = int(current_user_id)
            task.updated_at = datetime.now(UTC)
            db.add(task)
            updated_count += 1

            if old_status == "Unassigned" and new_status != "Unassigned":
                try:
                    BackgroundThreadPool.execute_task(
                        notify_deal_task_unassigned_status_change,
                        task.id,
                        old_status,
                        new_status,
                    )
                except Exception:
                    pass

    db.commit()

    if current_user_id:
        log_action(
            db,
            int(current_user_id),
            current_role or "USER",
            "BULK_UPDATED_STATUS",
            "DealTask",
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
