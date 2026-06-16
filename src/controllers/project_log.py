from sqlalchemy.orm import Session
from ..models.project_log import ProjectLog


def log_project_action(
    db: Session,
    user_id: int,
    user_role: str,
    action: str,
    entity_type: str,
    project_id: int,
    task_id: int | None = None,
    changes: dict | None = None
):
    """
    Append a project audit log entry to the current DB session.

    IMPORTANT: Does NOT commit — the caller is responsible for committing.
    This keeps the project log write in the same transaction as the
    triggering operation, eliminating an extra DB round-trip per write.
    """
    log = ProjectLog(
        user_id=user_id,
        user_role=user_role,
        action=action,
        entity_type=entity_type,
        project_id=project_id,
        task_id=task_id,
        changes=changes or {}
    )
    db.add(log)
    # ✅ No db.commit() here — caller commits; project log rides the same txn.