from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_, cast, String
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.project import Project, Task
from ..models.project_log import ProjectLog
from ..models.user import User

IST = ZoneInfo("Asia/Kolkata")

router = APIRouter(prefix="/project-logs", tags=["project-logs"])

KNOWN_USERS = {
    "3899927000000615348": "Ashok M",
    "3899927000000964875": "Suraj Gupta",
    "3899927000000882594": "Myisa Beiucy",
    "3899927000000201013": "Anslem Prathap",
    "3899927000005965002": "Subhasini TS",
    "3899927000000503894": "Saran D",
    "3899927000000135140": "Prathamesh Prakash",
    "3899927000000318361": "Namrata Srivastava",
    "3899927000000221552": "Sarada",
    "3899927000000527649": "Ambika",
    "1": "Anslem Prathap",
    "2": "Namrata Srivastava",
    "3": "Ravi Kumar",
    "4": "Priya Sharma",
}


def format_ist_datetime(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST).strftime("%d %b %Y, %I:%M %p")


@router.get("/analytics")
def get_project_logs_analytics(
    request: Request,
    time_range: Optional[str] = "30d",
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Returns aggregated analytics for project logs, task completion,
    user workload, people-wise activity breakdown, and project-wise distribution.
    """
    # 1. Fetch user map from database
    users_db = db.query(User.id, User.full_name, User.email, User.role).all()
    user_info_map = {
        str(u.id): {
            "name": u.full_name,
            "email": u.email,
            "role": u.role,
        }
        for u in users_db
    }

    def resolve_user_name(uid: Optional[str | int]) -> str:
        if uid is None:
            return "Unassigned"
        s_id = str(uid).strip()
        if s_id in user_info_map and user_info_map[s_id]["name"]:
            return user_info_map[s_id]["name"]
        if s_id in KNOWN_USERS:
            return KNOWN_USERS[s_id]
        return f"User #{s_id}"

    def resolve_user_meta(uid: Optional[str | int]) -> dict:
        if uid is None:
            return {"name": "Unassigned", "email": "", "role": "member"}
        s_id = str(uid).strip()
        name = resolve_user_name(s_id)
        email = user_info_map.get(s_id, {}).get("email", "")
        role = user_info_map.get(s_id, {}).get("role", "member")
        return {"name": name, "email": email, "role": role}

    # 2. Date Filtering
    now_utc = datetime.now(timezone.utc)
    start_dt = None
    if time_range == "7d":
        start_dt = now_utc - timedelta(days=7)
    elif time_range == "30d":
        start_dt = now_utc - timedelta(days=30)
    elif time_range == "90d":
        start_dt = now_utc - timedelta(days=90)

    # 3. Fetch Projects & Tasks
    projects_query = db.query(Project)
    if project_id and project_id.isdigit():
        projects_query = projects_query.filter(Project.id == int(project_id))
    all_projects = projects_query.order_by(Project.created_at.desc()).all()
    projects_map = {str(p.id): p for p in all_projects}

    tasks_query = db.query(Task)
    if project_id and project_id.isdigit():
        tasks_query = tasks_query.filter(Task.project_id == int(project_id))
    if user_id and user_id.isdigit():
        tasks_query = tasks_query.filter(Task.assignee_id == int(user_id))
    all_tasks = tasks_query.order_by(Task.created_at.desc()).all()
    tasks_map = {str(t.id): t for t in all_tasks}

    # 4. Fetch Logs
    logs_query = db.query(ProjectLog)
    if start_dt:
        logs_query = logs_query.filter(ProjectLog.created_at >= start_dt)
    if user_id and user_id.isdigit():
        logs_query = logs_query.filter(ProjectLog.user_id == int(user_id))
    if project_id and project_id.isdigit():
        logs_query = logs_query.filter(ProjectLog.project_id == int(project_id))

    all_logs = logs_query.order_by(ProjectLog.created_at.desc()).limit(2000).all()

    # 5. Global KPIs
    total_logs = len(all_logs)
    total_projects = len(all_projects)
    total_tasks = len(all_tasks)

    task_status_counts = {"done": 0, "in_progress": 0, "review": 0, "todo": 0}
    for t in all_tasks:
        st = str(t.status.value if hasattr(t.status, "value") else (t.status or "todo")).lower()
        if st in task_status_counts:
            task_status_counts[st] += 1
        elif "done" in st or "complete" in st:
            task_status_counts["done"] += 1
        elif "progress" in st:
            task_status_counts["in_progress"] += 1
        elif "review" in st:
            task_status_counts["review"] += 1
        else:
            task_status_counts["todo"] += 1

    completed_tasks = task_status_counts["done"]
    in_progress_tasks = task_status_counts["in_progress"]
    review_tasks = task_status_counts["review"]
    todo_tasks = task_status_counts["todo"]
    completion_rate = (
        round((completed_tasks / total_tasks) * 100, 1) if total_tasks > 0 else 0
    )

    # 6. Aggregations for Charts
    # User activity breakdown
    user_activity_counts = defaultdict(lambda: {"total": 0, "created": 0, "updated": 0, "commented": 0, "other": 0})
    action_type_counts = defaultdict(int)
    daily_trend = defaultdict(lambda: {"total": 0, "created": 0, "updated": 0, "commented": 0})

    for log in all_logs:
        u_str = str(log.user_id)
        act = (log.action or "UNKNOWN").upper()
        action_type_counts[act] += 1

        user_activity_counts[u_str]["total"] += 1
        if "CREATE" in act:
            user_activity_counts[u_str]["created"] += 1
        elif "UPDATE" in act:
            user_activity_counts[u_str]["updated"] += 1
        elif "COMMENT" in act:
            user_activity_counts[u_str]["commented"] += 1
        else:
            user_activity_counts[u_str]["other"] += 1

        if log.created_at:
            ist_dt = log.created_at.astimezone(IST) if log.created_at.tzinfo else log.created_at.replace(tzinfo=timezone.utc).astimezone(IST)
            date_key = ist_dt.strftime("%Y-%m-%d")
            daily_trend[date_key]["total"] += 1
            if "CREATE" in act:
                daily_trend[date_key]["created"] += 1
            elif "UPDATE" in act:
                daily_trend[date_key]["updated"] += 1
            elif "COMMENT" in act:
                daily_trend[date_key]["commented"] += 1

    # Task distribution by user
    user_tasks_counts = defaultdict(lambda: {"total": 0, "done": 0, "in_progress": 0, "review": 0, "todo": 0})
    for t in all_tasks:
        u_str = str(t.assignee_id) if t.assignee_id else "unassigned"
        st = str(t.status.value if hasattr(t.status, "value") else (t.status or "todo")).lower()
        user_tasks_counts[u_str]["total"] += 1
        if "done" in st or "complete" in st:
            user_tasks_counts[u_str]["done"] += 1
        elif "progress" in st:
            user_tasks_counts[u_str]["in_progress"] += 1
        elif "review" in st:
            user_tasks_counts[u_str]["review"] += 1
        else:
            user_tasks_counts[u_str]["todo"] += 1

    # Format Chart 1: User Activity Breakdown
    activity_by_user_chart = []
    # Collect all users from activity and task counts
    all_active_user_ids = set(user_activity_counts.keys()) | set(user_tasks_counts.keys())
    all_active_user_ids.discard("unassigned")

    for uid in all_active_user_ids:
        u_name = resolve_user_name(uid)
        act_info = user_activity_counts[uid]
        task_info = user_tasks_counts[uid]
        activity_by_user_chart.append({
            "user_id": uid,
            "user_name": u_name,
            "total_actions": act_info["total"],
            "created": act_info["created"],
            "updated": act_info["updated"],
            "commented": act_info["commented"],
            "tasks_assigned": task_info["total"],
            "tasks_completed": task_info["done"],
        })

    activity_by_user_chart.sort(key=lambda x: (x["total_actions"], x["tasks_completed"]), reverse=True)

    # Format Chart 2: Tasks by User
    tasks_by_user_chart = []
    for uid in all_active_user_ids:
        t_info = user_tasks_counts[uid]
        if t_info["total"] > 0:
            tasks_by_user_chart.append({
                "user_id": uid,
                "user_name": resolve_user_name(uid),
                "total": t_info["total"],
                "done": t_info["done"],
                "in_progress": t_info["in_progress"],
                "review": t_info["review"],
                "todo": t_info["todo"],
            })
    tasks_by_user_chart.sort(key=lambda x: x["total"], reverse=True)

    # Format Chart 3: Task Status Distribution (Donut Chart)
    task_status_distribution = [
        {"status": "done", "name": "Done", "count": completed_tasks, "fill": "#10b981"},
        {"status": "in_progress", "name": "In Progress", "count": in_progress_tasks, "fill": "#3b82f6"},
        {"status": "review", "name": "Review", "count": review_tasks, "fill": "#8b5cf6"},
        {"status": "todo", "name": "To Do", "count": todo_tasks, "fill": "#94a3b8"},
    ]

    # Format Chart 4: Daily Activity Timeline
    sorted_dates = sorted(daily_trend.keys())
    # If empty or fewer than 7 days, generate last 7 days window
    if len(sorted_dates) < 7:
        temp_date = (now_utc - timedelta(days=6)).astimezone(IST)
        for i in range(7):
            d_str = temp_date.strftime("%Y-%m-%d")
            if d_str not in daily_trend:
                daily_trend[d_str] = {"total": 0, "created": 0, "updated": 0, "commented": 0}
            temp_date += timedelta(days=1)
        sorted_dates = sorted(daily_trend.keys())

    activity_timeline = []
    for d_str in sorted_dates:
        parsed_d = datetime.strptime(d_str, "%Y-%m-%d")
        counts = daily_trend[d_str]
        activity_timeline.append({
            "date": d_str,
            "display_date": parsed_d.strftime("%d %b"),
            "total": counts["total"],
            "created": counts["created"],
            "updated": counts["updated"],
            "commented": counts["commented"],
        })

    # Format Chart 5: Project Workload
    project_workload = []
    for p in all_projects:
        p_id_str = str(p.id)
        p_tasks = [t for t in all_tasks if str(t.project_id) == p_id_str]
        p_done = sum(1 for t in p_tasks if str(t.status.value if hasattr(t.status, "value") else (t.status or "")).lower() in ("done", "completed"))
        p_in_prog = sum(1 for t in p_tasks if "progress" in str(t.status.value if hasattr(t.status, "value") else (t.status or "")).lower())
        
        # Calculate distinct contributors
        actioners = [str(a) for a in (p.actioner_ids or [])]
        assignees = [str(t.assignee_id) for t in p_tasks if t.assignee_id]
        all_members = set(actioners + assignees)
        if p.created_by:
            all_members.add(str(p.created_by))
        
        pct = round((p_done / len(p_tasks)) * 100) if p_tasks else 0
        project_workload.append({
            "project_id": p_id_str,
            "project_name": p.name,
            "status": str(p.status.value if hasattr(p.status, "value") else (p.status or "planning")),
            "priority": str(p.priority.value if hasattr(p.priority, "value") else (p.priority or "medium")),
            "total_tasks": len(p_tasks),
            "done_tasks": p_done,
            "in_progress_tasks": p_in_prog,
            "members_count": len(all_members),
            "completion_pct": pct,
        })
    project_workload.sort(key=lambda x: x["total_tasks"], reverse=True)

    # 7. People-Wise Detailed View
    people_summary = []
    for uid in all_active_user_ids:
        meta = resolve_user_meta(uid)
        u_logs = [l for l in all_logs if str(l.user_id) == uid]
        u_tasks = [t for t in all_tasks if str(t.assignee_id) == uid]
        
        # Determine which projects this person works on
        # 1. Actioner in project
        # 2. Assignee on any task in project
        # 3. Creator of project
        worked_projects = []
        for p in all_projects:
            is_actioner = uid in [str(a) for a in (p.actioner_ids or [])]
            is_creator = str(p.created_by) == uid
            user_p_tasks = [t for t in u_tasks if str(t.project_id) == str(p.id)]
            if is_actioner or is_creator or user_p_tasks:
                p_tasks_done = sum(1 for t in user_p_tasks if "done" in str(t.status.value if hasattr(t.status, "value") else (t.status or "")).lower())
                worked_projects.append({
                    "project_id": str(p.id),
                    "project_name": p.name,
                    "status": str(p.status.value if hasattr(p.status, "value") else (p.status or "active")),
                    "priority": str(p.priority.value if hasattr(p.priority, "value") else (p.priority or "medium")),
                    "tasks_count": len(user_p_tasks),
                    "done_count": p_tasks_done,
                    "is_actioner": is_actioner,
                    "is_creator": is_creator,
                })

        # Detailed tasks for this user
        tasks_details = []
        for t in u_tasks:
            p_obj = projects_map.get(str(t.project_id))
            tasks_details.append({
                "id": str(t.id),
                "title": t.title,
                "project_id": str(t.project_id),
                "project_name": p_obj.name if p_obj else f"Project #{t.project_id}",
                "status": str(t.status.value if hasattr(t.status, "value") else (t.status or "todo")),
                "priority": str(t.priority.value if hasattr(t.priority, "value") else (t.priority or "medium")),
                "type": str(t.type.value if hasattr(t.type, "value") else (t.type or "feature")),
                "created_at": format_ist_datetime(t.created_at),
                "actual_completion_date": format_ist_datetime(t.actual_completion_date),
            })

        # Recent activities for this user
        recent_activities = []
        for l in u_logs[:12]:
            p_obj = projects_map.get(str(l.project_id))
            t_obj = tasks_map.get(str(l.task_id))
            recent_activities.append({
                "id": str(l.id),
                "action": l.action,
                "entity_type": l.entity_type,
                "project_id": str(l.project_id) if l.project_id else None,
                "project_name": p_obj.name if p_obj else (f"Project #{l.project_id}" if l.project_id else None),
                "task_id": str(l.task_id) if l.task_id else None,
                "task_title": t_obj.title if t_obj else None,
                "changes": l.changes,
                "created_at": format_ist_datetime(l.created_at),
            })

        t_counts = user_tasks_counts[uid]
        people_summary.append({
            "user_id": uid,
            "user_name": meta["name"],
            "email": meta["email"],
            "role": meta["role"],
            "total_activities": user_activity_counts[uid]["total"],
            "activity_breakdown": user_activity_counts[uid],
            "task_counts": t_counts,
            "projects": worked_projects,
            "tasks": tasks_details,
            "recent_activities": recent_activities,
        })

    people_summary.sort(key=lambda x: (x["total_activities"], x["task_counts"]["total"]), reverse=True)

    # 8. Project-Wise Detailed View
    projects_summary = []
    for p in all_projects:
        p_id_str = str(p.id)
        p_tasks = [t for t in all_tasks if str(t.project_id) == p_id_str]
        p_logs = [l for l in all_logs if str(l.project_id) == p_id_str]

        # Members
        member_ids = set([str(a) for a in (p.actioner_ids or [])])
        for t in p_tasks:
            if t.assignee_id:
                member_ids.add(str(t.assignee_id))
        if p.created_by:
            member_ids.add(str(p.created_by))

        members_list = []
        for m_id in member_ids:
            m_tasks = [t for t in p_tasks if str(t.assignee_id) == m_id]
            m_done = sum(1 for t in m_tasks if "done" in str(t.status.value if hasattr(t.status, "value") else (t.status or "")).lower())
            members_list.append({
                "user_id": m_id,
                "user_name": resolve_user_name(m_id),
                "is_actioner": m_id in [str(a) for a in (p.actioner_ids or [])],
                "is_creator": str(p.created_by) == m_id,
                "tasks_count": len(m_tasks),
                "done_count": m_done,
            })
        members_list.sort(key=lambda x: x["tasks_count"], reverse=True)

        p_done = sum(1 for t in p_tasks if "done" in str(t.status.value if hasattr(t.status, "value") else (t.status or "")).lower())
        p_in_prog = sum(1 for t in p_tasks if "progress" in str(t.status.value if hasattr(t.status, "value") else (t.status or "")).lower())
        p_review = sum(1 for t in p_tasks if "review" in str(t.status.value if hasattr(t.status, "value") else (t.status or "")).lower())
        p_todo = sum(1 for t in p_tasks if "todo" in str(t.status.value if hasattr(t.status, "value") else (t.status or "")).lower())

        # Tasks list for this project
        project_tasks_list = []
        for t in p_tasks:
            project_tasks_list.append({
                "id": str(t.id),
                "title": t.title,
                "assignee_id": str(t.assignee_id) if t.assignee_id else None,
                "assignee_name": resolve_user_name(t.assignee_id) if t.assignee_id else "Unassigned",
                "status": str(t.status.value if hasattr(t.status, "value") else (t.status or "todo")),
                "priority": str(t.priority.value if hasattr(t.priority, "value") else (t.priority or "medium")),
                "created_at": format_ist_datetime(t.created_at),
                "actual_completion_date": format_ist_datetime(t.actual_completion_date),
            })

        # Recent activities for this project
        p_recent_logs = []
        for l in p_logs[:12]:
            t_obj = tasks_map.get(str(l.task_id))
            p_recent_logs.append({
                "id": str(l.id),
                "user_id": str(l.user_id),
                "user_name": resolve_user_name(l.user_id),
                "action": l.action,
                "entity_type": l.entity_type,
                "task_id": str(l.task_id) if l.task_id else None,
                "task_title": t_obj.title if t_obj else None,
                "changes": l.changes,
                "created_at": format_ist_datetime(l.created_at),
            })

        pct = round((p_done / len(p_tasks)) * 100) if p_tasks else 0
        projects_summary.append({
            "project_id": p_id_str,
            "project_name": p.name,
            "status": str(p.status.value if hasattr(p.status, "value") else (p.status or "planning")),
            "priority": str(p.priority.value if hasattr(p.priority, "value") else (p.priority or "medium")),
            "created_at": format_ist_datetime(p.created_at),
            "progress_pct": pct,
            "task_counts": {
                "total": len(p_tasks),
                "done": p_done,
                "in_progress": p_in_prog,
                "review": p_review,
                "todo": p_todo,
            },
            "members": members_list,
            "tasks": project_tasks_list,
            "recent_activities": p_recent_logs,
        })

    projects_summary.sort(key=lambda x: x["task_counts"]["total"], reverse=True)

    return {
        "kpis": {
            "total_logs": total_logs,
            "active_users_count": len(all_active_user_ids),
            "total_projects": total_projects,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "in_progress_tasks": in_progress_tasks,
            "review_tasks": review_tasks,
            "todo_tasks": todo_tasks,
            "completion_rate": completion_rate,
        },
        "charts": {
            "activity_by_user": activity_by_user_chart,
            "tasks_by_user": tasks_by_user_chart,
            "task_status_distribution": task_status_distribution,
            "activity_timeline": activity_timeline,
            "project_workload": project_workload,
            "action_type_distribution": [
                {"action": k, "count": v} for k, v in sorted(action_type_counts.items(), key=lambda x: x[1], reverse=True)
            ],
        },
        "people": people_summary,
        "projects": projects_summary,
    }


@router.get("")
def get_project_logs(
    request: Request,
    page: int = 1,
    limit: int = 20,
    user_id: Optional[str] = None,
    project_id: Optional[str] = None,
    task_id: Optional[str] = None,
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    offset = (page - 1) * limit

    query = db.query(ProjectLog)

    if user_id and user_id.isdigit():
        query = query.filter(ProjectLog.user_id == int(user_id))

    if project_id and project_id.isdigit():
        query = query.filter(ProjectLog.project_id == int(project_id))

    if task_id and task_id.isdigit():
        query = query.filter(ProjectLog.task_id == int(task_id))

    if action:
        query = query.filter(ProjectLog.action.ilike(f"%{action.strip()}%"))

    if entity_type:
        query = query.filter(ProjectLog.entity_type.ilike(f"%{entity_type.strip()}%"))

    if search:
        s_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                ProjectLog.action.ilike(s_term),
                ProjectLog.entity_type.ilike(s_term),
                cast(ProjectLog.project_id, String).ilike(s_term),
                cast(ProjectLog.task_id, String).ilike(s_term),
                cast(ProjectLog.user_id, String).ilike(s_term),
            )
        )

    total = query.count()
    logs = (
        query.order_by(ProjectLog.created_at.desc())
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
        "page_info": {"page": page, "limit": limit, "total": total},
    }
