from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo
IST = ZoneInfo("Asia/Kolkata")
from ..database import get_db
from ..models.audit_log import AuditLog

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("")
def get_audit_logs(request: Request, page: int = 1, db: Session = Depends(get_db)):
    raw_role = str(getattr(request.state, "role", "")).lower().strip().replace(" ", "_")
    is_super_admin = (
        raw_role in ["super_admin", "superadmin"]
        or "super_admin" in raw_role
        or "superadmin" in raw_role
    )
    if not is_super_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    limit = 20
    offset = (page - 1) * limit

    company_filter = [or_(AuditLog.company_id == 1, AuditLog.company_id.is_(None))]

    total = db.query(AuditLog).filter(*company_filter).count()
    logs = (
        db.query(AuditLog)
        .filter(*company_filter)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "data": [
            {
                "id": str(log.id),
                "company_id": log.company_id or 1,
                "user_id": str(log.user_id),
                "user_role": log.user_role,
                "action": log.action,
                "entity": log.entity,
                "entity_id": str(log.entity_id),
                "payload": log.payload,
                "created_at": log.created_at.astimezone(IST).strftime("%d %b %Y, %I:%M %p"),
            }
            for log in logs
        ],
        "page_info": {"page": page, "total": total},
    }
