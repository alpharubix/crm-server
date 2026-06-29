import logging
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from src.controllers.Background_threads import BackgroundThreadPool

from ..controllers.mail import (
    notify_project_approved,
    notify_project_completed,
    notify_project_pending_review,
)
from ..controllers.project_log import log_project_action
from ..database import get_db
from ..models.project import Project, ProjectComment, StatusEnum, Task, TaskComment
from ..models.project_log import ProjectLog
from ..models.user import User

IST = ZoneInfo("Asia/Kolkata")
router = APIRouter(prefix="/projects", tags=["projects"])
logger = logging.getLogger(__name__)


def format_project(p) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "description": p.description,
        "priority": p.priority,
        "status": p.status,
        "created_by": str(p.created_by),
        "modified_by": str(p.modified_by) if p.modified_by else None,
        "approver_id": str(p.approver_id),
        "created_at": p.created_at.astimezone(IST).strftime("%d %b %Y, %I:%M %p"),
        "modified_at": p.modified_at.astimezone(IST).strftime("%d %b %Y, %I:%M %p")
        if p.modified_at
        else None,
        "start_date": p.start_date.strftime("%Y-%m-%d") if p.start_date else None,
        "end_date": p.end_date.strftime("%Y-%m-%d") if p.end_date else None,
        "actioner_ids": [str(i) for i in (p.actioner_ids or [])],
        "project_type": p.project_type,
        "attachment_links": p.attachment_links or [],
    }


@router.post("")
@router.post("/")
async def create_project(request: Request, db: Session = Depends(get_db)):
    # 1. Authorization Check
    if request.state.role == "executive":
        raise HTTPException(status_code=401, detail="Unauthorized access")

    body = await request.json()

    # 2. Validation
    if not body.get("name"):
        raise HTTPException(status_code=400, detail="name is required")
    if not body.get("approver_id"):
        raise HTTPException(status_code=400, detail="approver_id is required")

    # 3. Explicit Mapping
    project = Project(
        name=body["name"],
        description=body.get("description"),
        priority=body.get("priority"),
        status=body.get("status", "pending_for_approve"),
        created_by=request.state.user_id,
        approver_id=int(body["approver_id"]),
        start_date=body.get("start_date"),
        end_date=body.get("end_date"),
        actioner_ids=[int(i) for i in body.get("actioner_ids", [])],
        project_type=body.get("project_type"),
        attachment_links=body.get("attachment_links", []),
    )

    db.add(project)
    db.commit()
    db.refresh(project)

    # 4. Target Trigger Update: Notify Team Members (actioner_ids) instead of just the Approver
    if project.actioner_ids:
        # Fetch all Team Member users and extract unique valid emails
        team_members = db.query(User).filter(User.id.in_(project.actioner_ids)).all()
        team_emails = list({user.email for user in team_members if user.email})

        if team_emails:
            # We pass the list to our non-blocking pool so the user doesn't face API delays
            # BackgroundThreadPool.execute_task(
            #     notify_project_approved,  # Reusing your list engine function to mail the team
            #     emails=team_emails,
            #     project_name=project.name,
            #     project_id=project.id,
            # )
            logger.info(
                f"Dispatched background creation alerts to team members: {team_emails}"
            )

    # 5. Audit Logging
    log_project_action(
        db,
        request.state.user_id,
        request.state.role,
        "CREATED",
        "PROJECT",
        project.id,
        None,
        changes=body,
    )
    return format_project(project)


@router.get("")
@router.get("/")
def get_projects(
    request: Request,
    page: int = 1,
    search: Optional[str] = None,
    assignee_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    project_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    if request.state.role == "executive":
        raise HTTPException(status_code=401, detail="Unauthorized Access")

    user_id = request.state.user_id
    limit = 50
    offset = (page - 1) * limit

    # Users who always have full visibility across all projects
    SUPER_APPROVER_IDS = [3899927000000201013, 3899927000005965002]

    # 1. Base Authorization Filter
    # Super-approvers skip the ownership filter — they see all projects.
    if user_id in SUPER_APPROVER_IDS:
        query = db.query(Project)
    else:
        query = db.query(Project).filter(
            (Project.created_by == user_id)
            | (Project.approver_id == user_id)
            | (Project.actioner_ids.any(user_id))
        )

    # 2. Apply Dynamic Filters
    if search:
        query = query.filter(Project.name.ilike(f"%{search}%"))
    if assignee_id:
        query = query.filter(Project.actioner_ids.any(assignee_id))
    if start_date:
        query = query.filter(Project.start_date >= start_date)
    if end_date:
        query = query.filter(Project.end_date <= end_date)
    if project_type:
        query = query.filter(Project.project_type == project_type)
    if status:
        query = query.filter(Project.status == status)

    total = query.count()
    projects = (
        query.order_by(Project.created_at.desc()).offset(offset).limit(limit).all()
    )

    return {
        "data": [format_project(p) for p in projects],
        "page_info": {"page": page, "total": total},
    }


@router.get("/{project_id}")
def get_project(request: Request, project_id: int, db: Session = Depends(get_db)):
    if request.state.role == "executive":
        raise HTTPException(status_code=401, detail="Unauthorized Access")

    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 1. Fetch standalone Project Comments (Ordered oldest first for chat view)
    project_comments = (
        db.query(ProjectComment)
        .filter(ProjectComment.project_id == project_id)
        .order_by(ProjectComment.created_at.asc())
        .all()
    )

    # 2. Fetch all Task IDs under this project for cascading history
    task_ids = [t.id for t in project.tasks]

    # 3. Query ALL task comments for those IDs + order by newest first
    cascading_comments = []
    if task_ids:
        comments = (
            db.query(TaskComment)
            .filter(TaskComment.task_id.in_(task_ids))
            .order_by(TaskComment.created_at.desc())
            .all()
        )
        cascading_comments = [format_comment(c) for c in comments]

    # 4. Compile the full unified response payload
    response_data = format_project(project)
    response_data["project_comments"] = [
        format_project_comment(c) for c in project_comments
    ]
    response_data["cascading_comments"] = cascading_comments

    return response_data


@router.patch("/{project_id}")
async def update_project(
    project_id: int, request: Request, db: Session = Depends(get_db)
):
    if request.state.role == "executive":
        raise HTTPException(status_code=401, detail="Unauthorised Access")

    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    body = await request.json()

    # 1. Standard string/enum fields
    allowed = [
        "name",
        "description",
        "priority",
        "status",
        "project_type",
        "attachment_links",
    ]
    for field in allowed:
        if field in body:
            setattr(project, field, body[field])

    # 2. Handle integer casting for IDs
    if "approver_id" in body and body["approver_id"]:
        setattr(project, "approver_id", int(body["approver_id"]))

    if "actioner_ids" in body:
        setattr(project, "actioner_ids", [int(i) for i in body["actioner_ids"]])

    # 3. Handle Dates
    if "start_date" in body:
        project.start_date = body["start_date"]
    if "end_date" in body:
        project.end_date = body["end_date"]

    project.modified_by = request.state.user_id
    db.commit()
    db.refresh(project)

    # --- EMAIL NOTIFICATION TRIGGERS (Offloaded to BackgroundThreadPool) ---

    # Trigger A: Project Approved (Moved to planning)
    if project.status == StatusEnum.planning:
        logger.info("statusenum: %s %s", project.status, StatusEnum.planning)
        actioners = db.query(User).filter(User.id.in_(project.actioner_ids)).all()
        emails = list({user.email for user in actioners if user.email})

        # if emails:
            # BackgroundThreadPool.execute_task(
            #     notify_project_approved,
            #     emails=emails,
            #     project_name=project.name,
            #     project_id=project.id,
            # )

    # Trigger B: Project Pending Review
    # if project.status == StatusEnum.pending_for_review:
    #     approver = db.query(User).filter(User.id == project.approver_id).first()

    #     if approver and approver.email:
            # BackgroundThreadPool.execute_task(
            #     notify_project_pending_review,
            #     approver_email=approver.email,
            #     approver_name=approver.full_name,
            #     project_name=project.name,
            #     project_id=project.id,
            # )

    # Trigger C: NEW REQUIRED STATUS - Project Completed
    # Notifies: Team Members (actioners) + Approver + Initiator (created_by)
    if project.status == StatusEnum.completed:
        logger.info("Project completed: %s", project.name)

        # Collect distinct user IDs for all 3 target roles
        stakeholder_ids = set()
        if project.actioner_ids:
            stakeholder_ids.update(project.actioner_ids)
        if project.approver_id:
            stakeholder_ids.add(project.approver_id)
        if project.created_by:
            stakeholder_ids.add(project.created_by)

        # Extract unique emails from database
        # stakeholders = db.query(User).filter(User.id.in_(list(stakeholder_ids))).all()
        # notification_emails = list({u.email for u in stakeholders if u.email})

        # if notification_emails:
            # BackgroundThreadPool.execute_task(
            #     notify_project_completed,  # Extracted to the thread pool cleanly
            #     emails=notification_emails,
            #     project_name=project.name,
            #     project_id=project.id,
            # )
            # logger.info(f"Dispatched completion alerts to: {notification_emails}")

    # 4. Audit Logging
    log_project_action(
        db,
        request.state.user_id,
        request.state.role,
        "UPDATED",
        "PROJECT",
        project.id,
        None,
        body,
    )
    return format_project(project)


@router.delete("/{project_id}")
def delete_project(project_id: int, request: Request, db: Session = Depends(get_db)):
    if request.state.role == "executive":
        raise HTTPException(status_code=401, detail="Unauthorised access")
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()

    return {"message": "Project deleted"}


def format_project_comment(c) -> dict:
    return {
        "id": str(c.id),
        "project_id": str(c.project_id),
        "user_id": str(c.user_id),
        "content": c.content,
        "created_at": c.created_at.astimezone(IST).strftime("%d %b %Y, %I:%M %p"),
        "user_name": c.user.full_name if c.user else None,
    }


# 1. POST: Add a comment directly to the project
@router.post("/{project_id}/comments")
async def add_project_comment(
    project_id: int, request: Request, db: Session = Depends(get_db)
):
    user_id = request.state.user_id
    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    body = await request.json()
    if not body.get("content"):
        raise HTTPException(status_code=400, detail="content is required")

    comment = ProjectComment(
        project_id=project_id, user_id=user_id, content=body["content"]
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    log_project_action(
        db,
        request.state.user_id,
        request.state.role,
        "COMMENTED",
        "PROJECT_COMMENT",
        project_id,
        None,
        changes={"content": body["content"]},
    )
    return format_project_comment(comment)


# 2. GET: Fetch standalone project comments
@router.get("/{project_id}/comments")
def get_project_comments(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 1. Standalone project comments
    p_comments = (
        db.query(ProjectComment)
        .filter(ProjectComment.project_id == project_id)
        .order_by(ProjectComment.created_at.asc())
        .all()
    )

    # 2. Gather aggregate nested task comments
    task_ids = [t.id for t in project.tasks]
    cascading_task_comments = []
    if task_ids:
        t_comments = (
            db.query(TaskComment)
            .filter(TaskComment.task_id.in_(task_ids))
            .order_by(TaskComment.created_at.desc())
            .all()
        )
        cascading_task_comments = [format_comment(c) for c in t_comments]

    return {
        "project_comments": [format_project_comment(c) for c in p_comments],
        "cascading_task_comments": cascading_task_comments,
    }


def format_task(t) -> dict:
    return {
        "id": str(t.id),
        "title": t.title,
        "description": t.description,
        "type": t.type,
        "priority": t.priority,
        "status": t.status,
        "project_id": str(t.project_id),
        "assignee_id": str(t.assignee_id) if t.assignee_id else None,
        "created_by": str(t.created_by),
        "modified_by": str(t.modified_by) if t.modified_by else None,
        "created_at": t.created_at.astimezone(IST).strftime("%d %b %Y, %I:%M %p"),
        "modified_at": t.modified_at.astimezone(IST).strftime("%d %b %Y, %I:%M %p")
        if t.modified_at
        else None,
        "start_date": t.start_date.strftime("%Y-%m-%d") if t.start_date else None,
        "end_date": t.end_date.strftime("%Y-%m-%d") if t.end_date else None,
        "actual_completion_date": t.actual_completion_date.strftime("%Y-%m-%d")
        if t.actual_completion_date
        else None,
        "attachment_links": t.attachment_links or [],
        "assignee_name": t.assignee.full_name if t.assignee else None,
    }


@router.post("/{project_id}/tasks")
async def create_task(project_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.state.user_id

    if request.state.role == "executive":
        raise HTTPException(status_code=401, detail="Unauthorised Access")

    project = db.query(Project).filter(Project.id == project_id).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # --- CHANGED: Allow Owner, Approver, OR Assignee ---
    is_member = (
        user_id == project.created_by
        or user_id == project.approver_id
        or user_id in (project.actioner_ids or [])
    )

    if not is_member:
        raise HTTPException(
            status_code=403, detail="Only project members can create tasks"
        )
    # ---------------------------------------------------

    body = await request.json()

    if not body.get("title"):
        raise HTTPException(status_code=400, detail="title is required")

    task = Task(
        title=body["title"],
        description=body.get("description"),
        type=body.get("type", "feature"),
        priority=body.get("priority"),
        status=body.get("status", "todo"),
        project_id=project_id,
        # CHANGED: Cast string ID to int
        assignee_id=int(body["assignee_id"]) if body.get("assignee_id") else None,
        created_by=request.state.user_id,
        start_date=body.get("start_date"),
        end_date=body.get("end_date"),
        attachment_links=body.get("attachment_links", []),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    log_project_action(
        db,
        request.state.user_id,
        request.state.role,
        "CREATED",
        "TASK",
        project_id,
        task.id,
        changes=body,
    )
    return format_task(task)


@router.get("/{project_id}/tasks")
def get_tasks(
    project_id: int,
    assignee_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    query = db.query(Task).filter(Task.project_id == project_id)

    if assignee_id:
        query = query.filter(Task.assignee_id == assignee_id)
    if status:
        query = query.filter(Task.status == status)

    tasks = query.order_by(Task.created_at.desc()).all()

    return {"data": [format_task(t) for t in tasks]}


@router.patch("/{project_id}/tasks/{task_id}")
async def update_task(
    project_id: int, task_id: int, request: Request, db: Session = Depends(get_db)
):
    user_id = request.state.user_id

    if request.state.role == "executive":
        raise HTTPException(status_code=401, detail="Unauthorised Access")

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task = (
        db.query(Task).filter(Task.id == task_id, Task.project_id == project_id).first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    body = await request.json()

    # --- CHANGED: Check if user is any type of project member ---
    is_member = (
        user_id == project.created_by
        or user_id == project.approver_id
        or user_id in (project.actioner_ids or [])
    )

    if not is_member:
        raise HTTPException(
            status_code=403, detail="Only project members can edit tasks"
        )

    # --- CHANGED: All members get full edit access ---
    allowed = [
        "title",
        "description",
        "type",
        "priority",
        "status",
        "assignee_id",
        "start_date",
        "end_date",
        "actual_completion_date",
        "attachment_links",
    ]

    for field in allowed:
        if field in body:
            # Cast assignee_id to int if it's provided
            if field == "assignee_id" and body[field] is not None:
                setattr(task, field, int(body[field]))
            else:
                setattr(task, field, body[field])

    task.modified_by = user_id
    if body.get("status") == "done" and not task.actual_completion_date:  # type: ignore
        setattr(task, "actual_completion_date", datetime.now(IST))
    db.commit()
    db.refresh(task)

    # ── Auto-move project to pending_for_review if all tasks are done ──
    # if body.get("status") == "done":
    #     all_tasks = db.query(Task).filter(Task.project_id == project_id).all()
    #     if len(all_tasks) > 0 and all(t.status == "done" for t in all_tasks):
    #         setattr(project, "status", "pending_for_review")
    #         setattr(project, "modified_by", user_id)
    #         db.commit()
    log_project_action(
        db,
        request.state.user_id,
        request.state.role,
        "UPDATED",
        "TASK",
        project_id,
        task.id,
        body,
    )
    return format_task(task)


@router.delete("/{project_id}/tasks/{task_id}")
def delete_task(
    project_id: int, task_id: int, request: Request, db: Session = Depends(get_db)
):
    if request.state.role == "executive":
        raise HTTPException(status_code=401, detail="Unauthorised Access")

    task = (
        db.query(Task).filter(Task.id == task_id, Task.project_id == project_id).first()
    )
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()

    return {"message": "Task deleted"}


def format_comment(c) -> dict:
    return {
        "id": str(c.id),
        "task_id": str(c.task_id),
        "user_id": str(c.user_id),
        "content": c.content,
        "created_at": c.created_at.astimezone(IST).strftime("%d %b %Y, %I:%M %p"),
        "user_name": c.user.full_name if c.user else None,
    }


@router.post("/{project_id}/tasks/{task_id}/comments")
async def add_task_comment(
    project_id: int, task_id: int, request: Request, db: Session = Depends(get_db)
):
    user_id = request.state.user_id

    project = db.query(Project).filter(Project.id == project_id).first()
    task = (
        db.query(Task).filter(Task.id == task_id, Task.project_id == project_id).first()
    )

    if not project or not task:
        raise HTTPException(status_code=404, detail="Project or Task not found")

    is_member = (
        user_id == project.created_by
        or user_id == project.approver_id
        or user_id in (project.actioner_ids or [])
    )

    if not is_member:
        raise HTTPException(
            status_code=403, detail="Unauthorized to comment on this task"
        )

    body = await request.json()
    if not body.get("content"):
        raise HTTPException(status_code=400, detail="content is required")

    comment = TaskComment(task_id=task_id, user_id=user_id, content=body["content"])
    db.add(comment)
    db.commit()
    db.refresh(comment)
    log_project_action(
        db,
        request.state.user_id,
        request.state.role,
        "COMMENTED",
        "COMMENT",
        project_id,
        task_id,
        changes={"content": body["content"]},
    )
    return format_comment(comment)


@router.get("/{project_id}/tasks/{task_id}/comments")
def get_task_comments(
    project_id: int, task_id: int, request: Request, db: Session = Depends(get_db)
):
    # Optional: Add the same ownership/assignee validation here if comments are strictly private

    comments = (
        db.query(TaskComment)
        .filter(TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at.asc())
        .all()
    )

    return {"data": [format_comment(c) for c in comments]}


# LOGS
@router.get("/{project_id}/logs")
def get_project_logs(project_id: int, request: Request, db: Session = Depends(get_db)):
    if request.state.role == "executive":
        raise HTTPException(status_code=401, detail="Unauthorized")

    logs = (
        db.query(ProjectLog)
        .filter(ProjectLog.project_id == project_id)
        .order_by(ProjectLog.created_at.desc())
        .all()
    )

    formatted_logs = [
        {
            "id": str(log.id),
            "project_id": str(log.project_id),
            "task_id": str(log.task_id) if log.task_id else None,
            "user_id": str(log.user_id),
            "user_role": log.user_role,
            "action": log.action,
            "entity_type": log.entity_type,
            "changes": log.changes,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
    return {"data": formatted_logs}


@router.get("/{project_id}/tasks/{task_id}/logs")
def get_task_logs(
    project_id: int, task_id: int, request: Request, db: Session = Depends(get_db)
):
    if request.state.role == "executive":
        raise HTTPException(status_code=401, detail="Unauthorized")

    logs = (
        db.query(ProjectLog)
        .filter(ProjectLog.task_id == task_id)
        .order_by(ProjectLog.created_at.desc())
        .all()
    )

    formatted_logs = [
        {
            "id": str(log.id),
            "project_id": str(log.project_id),
            "task_id": str(log.task_id) if log.task_id else None,
            "user_id": str(log.user_id),
            "user_role": log.user_role,
            "action": log.action,
            "entity_type": log.entity_type,
            "changes": log.changes,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
    return {"data": formatted_logs}
