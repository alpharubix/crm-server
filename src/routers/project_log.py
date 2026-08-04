from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from zoneinfo import ZoneInfo

from ..database import get_db
from ..models.project import Project, Task
from ..models.project_log import ProjectLog

IST = ZoneInfo("Asia/Kolkata")

router = APIRouter(prefix="/project-logs", tags=["project-logs"])


@router.get("")
def get_project_logs(
    request: Request, page: int = 1, db: Session = Depends(get_db)
):
    limit = 20
    offset = (page - 1) * limit

    total = db.query(ProjectLog).count()
    logs = (
        db.query(ProjectLog)
        .order_by(ProjectLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    project_ids = list({l.project_id for l in logs if l.project_id})
    task_ids = list({l.task_id for l in logs if l.task_id})

    projects_map = {}
    if project_ids:
        projects = (
            db.query(Project.id, Project.name)
            .filter(Project.id.in_(project_ids))
            .all()
        )
        projects_map = {str(p.id): p.name for p in projects}

    tasks_map = {}
    if task_ids:
        tasks = (
            db.query(Task.id, Task.title).filter(Task.id.in_(task_ids)).all()
        )
        tasks_map = {str(t.id): t.title for t in tasks}

    return {
        "data": [
            {
                "id": str(log.id),
                "project_id": str(log.project_id) if log.project_id else None,
                "project_name": projects_map.get(str(log.project_id)),
                "task_id": str(log.task_id) if log.task_id else None,
                "task_title": tasks_map.get(str(log.task_id)),
                "user_id": str(log.user_id),
                "user_role": log.user_role,
                "action": log.action,
                "entity_type": log.entity_type,
                "changes": log.changes,
                "created_at": log.created_at.astimezone(IST).strftime(
                    "%d %b %Y, %I:%M %p"
                )
                if log.created_at
                else None,
            }
            for log in logs
        ],
        "page_info": {"page": page, "total": total},
    }
