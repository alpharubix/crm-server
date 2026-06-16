from sqlalchemy.orm import Session
from ..models.audit_log import AuditLog


def log_action(
    db: Session,
    user_id: int,
    user_role: str,
    action: str,
    entity: str,
    entity_id: int,
    payload: dict,
):
    """
    Append an audit log entry to the current DB session.

    IMPORTANT: Does NOT commit — the caller is responsible for committing.
    This keeps the audit log write in the same transaction as the triggering
    operation, eliminating an extra DB round-trip per write.
    """
    log = AuditLog(
        user_id=user_id,
        user_role=user_role,
        action=action,
        entity=entity,
        entity_id=entity_id,
        payload=payload,
    )
    db.add(log)
    # ✅ No db.commit() here — caller commits; audit log rides the same txn.