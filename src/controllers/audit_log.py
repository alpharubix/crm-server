from fastapi.encoders import jsonable_encoder
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models.audit_log import AuditLog


def ensure_audit_log_company_id_column(db: Session):
    try:
        db.execute(
            text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS company_id INTEGER DEFAULT 1;")
        )
        db.commit()
    except Exception:
        db.rollback()


def log_action(
    db: Session,
    user_id: int,
    user_role: str,
    action: str,
    entity: str,
    entity_id: int,
    payload: dict,
    company_id: int = 1,
):
    safe_payload = jsonable_encoder(payload) if payload is not None else {}
    log = AuditLog(
        company_id=company_id,
        user_id=user_id,
        user_role=user_role,
        action=action,
        entity=entity,
        entity_id=entity_id,
        payload=safe_payload,
    )
    db.add(log)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        err_msg = str(e).lower()
        if "company_id" in err_msg or "undefinedcolumn" in err_msg:
            ensure_audit_log_company_id_column(db)
            log = AuditLog(
                company_id=company_id,
                user_id=user_id,
                user_role=user_role,
                action=action,
                entity=entity,
                entity_id=entity_id,
                payload=safe_payload,
            )
            db.add(log)
            db.commit()
        else:
            raise e
