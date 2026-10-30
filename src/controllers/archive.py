import math
from datetime import datetime, timezone
from typing import Any, Tuple, Type
from fastapi import HTTPException
from sqlalchemy import or_, desc
from sqlalchemy.orm import Session

from src.controllers.audit_log import log_action
from src.models.account import Account
from src.models.deal import Deal
from src.models.contact import Contact
from src.models.ticket import Ticket
from src.models.revenue import Revenue
from src.models.account_task import AccountTask
from src.models.deal_task import DealTask
from src.models.deal_document import DealDocument
from src.models.user import User
from src.utility.archive_visibility import is_super_admin


ENTITY_MAP: dict[str, dict[str, Any]] = {
    "accounts": {
        "model": Account,
        "name_attr": "account_name",
        "entity_name": "Account",
    },
    "deals": {
        "model": Deal,
        "name_attr": "deal_name",
        "entity_name": "Deal",
    },
    "contacts": {
        "model": Contact,
        "name_attr": "last_name",
        "entity_name": "Contact",
    },
    "tickets": {
        "model": Ticket,
        "name_attr": "ticket_name",
        "entity_name": "Ticket",
    },
    "revenue": {
        "model": Revenue,
        "name_attr": "account_name",
        "entity_name": "Revenue",
    },
    "account_tasks": {
        "model": AccountTask,
        "name_attr": "task_type",
        "entity_name": "AccountTask",
    },
    "deal_tasks": {
        "model": DealTask,
        "name_attr": "task_type",
        "entity_name": "DealTask",
    },
    "deal_documents": {
        "model": DealDocument,
        "name_attr": "module",
        "entity_name": "DealDocument",
    },
}


def _get_entity_config(module: str) -> dict[str, Any]:
    normalized_module = module.lower().strip().replace("-", "_")
    if normalized_module in ENTITY_MAP:
        return ENTITY_MAP[normalized_module]
    # Check singular forms
    singular_map = {
        "account": "accounts",
        "deal": "deals",
        "contact": "contacts",
        "ticket": "tickets",
        "revenues": "revenue",
        "account_task": "account_tasks",
        "deal_task": "deal_tasks",
        "deal_document": "deal_documents",
        "deal_docs": "deal_documents",
    }
    if normalized_module in singular_map:
        return ENTITY_MAP[singular_map[normalized_module]]
    raise HTTPException(status_code=400, detail=f"Unsupported module: {module}")


def archive_record(
    db: Session,
    module: str,
    record_id: int,
    user_id: int,
    user_role: str,
    reason: str | None = None,
) -> dict[str, Any]:
    config = _get_entity_config(module)
    model = config["model"]
    entity_name = config["entity_name"]

    record = db.query(model).filter(model.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"{entity_name} with ID {record_id} not found")

    if record.archived_at is not None:
        raise HTTPException(
            status_code=400, detail=f"{entity_name} #{record_id} is already archived"
        )

    now = datetime.now(timezone.utc)
    record.archived_at = now
    record.archived_by_id = int(user_id)

    db.commit()
    db.refresh(record)

    # Log action
    log_action(
        db=db,
        user_id=int(user_id),
        user_role=user_role,
        action="ARCHIVE",
        entity=entity_name,
        entity_id=record_id,
        payload={"reason": reason, "archived_at": now.isoformat()},
    )

    return {
        "success": True,
        "message": f"{entity_name} archived successfully",
        "id": record.id,
        "module": module,
        "archived_at": record.archived_at,
    }


def restore_record(
    db: Session,
    module: str,
    record_id: int,
    user_id: int,
    user_role: str,
) -> dict[str, Any]:
    # Strictly Super Admin
    if not is_super_admin(user_role):
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Only Super Admin can restore archived records",
        )

    config = _get_entity_config(module)
    model = config["model"]
    entity_name = config["entity_name"]

    record = db.query(model).filter(model.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail=f"{entity_name} with ID {record_id} not found")

    if record.archived_at is None:
        raise HTTPException(
            status_code=400, detail=f"{entity_name} #{record_id} is not independently archived"
        )

    # Restore independent status
    record.archived_at = None
    record.archived_by_id = None

    db.commit()
    db.refresh(record)

    # Log action
    log_action(
        db=db,
        user_id=int(user_id),
        user_role=user_role,
        action="RESTORE",
        entity=entity_name,
        entity_id=record_id,
        payload={"restored_at": datetime.now(timezone.utc).isoformat()},
    )

    return {
        "success": True,
        "message": f"{entity_name} restored successfully",
        "id": record.id,
        "module": module,
    }


def get_archived_list(
    db: Session,
    module: str,
    user_role: str,
    page: int = 1,
    page_size: int = 30,
    search: str | None = None,
) -> dict[str, Any]:
    # Strictly Super Admin
    if not is_super_admin(user_role):
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Only Super Admin can view archived records",
        )

    config = _get_entity_config(module)
    model = config["model"]
    entity_name = config["entity_name"]
    name_attr = config["name_attr"]

    query = db.query(model).filter(model.archived_at.isnot(None))

    if search and search.strip():
        term = f"%{search.strip()}%"
        if hasattr(model, name_attr):
            query = query.filter(getattr(model, name_attr).ilike(term))

    total_count = query.count()
    offset = (page - 1) * page_size
    records = query.order_by(desc(model.archived_at)).offset(offset).limit(page_size).all()

    # Pre-fetch user map for archived_by_id
    user_ids = {r.archived_by_id for r in records if r.archived_by_id}
    user_map = {}
    if user_ids:
        users = db.query(User.id, User.full_name, User.email).filter(User.id.in_(user_ids)).all()
        user_map = {u.id: (u.full_name or u.email) for u in users}

    items = []
    for r in records:
        name_val = getattr(r, name_attr, None)
        if not name_val and hasattr(r, "id"):
            name_val = f"#{r.id}"
        
        details = {}
        if hasattr(r, "account_name") and r.account_name:
            details["account_name"] = r.account_name
        if hasattr(r, "deal_name") and r.deal_name:
            details["deal_name"] = r.deal_name
        if hasattr(r, "email") and r.email:
            details["email"] = r.email
        if hasattr(r, "amount") and r.amount is not None:
            details["amount"] = r.amount

        items.append({
            "id": r.id,
            "name": str(name_val) if name_val else f"#{r.id}",
            "module": module,
            "archived_at": r.archived_at,
            "archived_by_id": r.archived_by_id,
            "archived_by_name": user_map.get(r.archived_by_id, "Unknown"),
            "details": details,
        })

    total_pages = math.ceil(total_count / page_size) if total_count > 0 else 1

    return {
        "success": True,
        "data": items,
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
