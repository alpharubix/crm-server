import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy import and_
from sqlalchemy.orm import Session, selectinload
from starlette.requests import Request

from src.controllers.notes import get_notes
from src.models.hiring import Candidate, JobRequirement

# ── ID Precision Fix Helper ──────────────────────────────────────


def stringify_ids(data):
    if isinstance(data, list):
        return [stringify_ids(item) for item in data]
    if hasattr(data, "__dict__"):
        res = {c.name: getattr(data, c.name) for c in data.__table__.columns}

        for rel in ["approver", "assignee", "created_by", "submitted_by_user"]:
            if rel in data.__dict__:
                val = getattr(data, rel)
                if val:
                    res[rel] = {
                        "id": str(val.id),
                        "name": getattr(
                            val, "name", getattr(val, "username", str(val.id))
                        ),
                    }
        return stringify_ids(res)

    if isinstance(data, dict):
        new_data = {}
        for k, v in data.items():
            if (k == "id" or k.endswith("_id")) and isinstance(v, int):
                new_data[k] = str(v)
            elif isinstance(v, (dict, list)):
                new_data[k] = stringify_ids(v)
            else:
                new_data[k] = v
        return new_data
    return data


# ── Job Requirement ──────────────────────────────────────────────

# ── EXPLICIT HR DEPT BYPASS REGISTRY ──
HR_USER_IDS = [
    "3899927000000318361",
    "3899927000000221552",
    "3899927000000527649",
]  # Namrata, Sarada, Ambika strings


def create_job_requirement(
    db: Session, data: Dict[str, Any], user_id: int, user_role: str
):
    # Allow transaction if they are a Super Admin/Admin OR if their specific ID belongs to the HR Team array
    is_hr_personnel = str(user_id) in HR_USER_IDS

    if user_role == "executive" and not is_hr_personnel:
        raise HTTPException(status_code=401, detail="Unauthorized access")

    if not data.get("hiring_position"):
        raise HTTPException(status_code=400, detail="hiring_position is required")

    # Force initial workflow state on creation
    data["status"] = "pending_approval"

    jr = JobRequirement(**data, created_by_id=user_id)
    db.add(jr)
    db.commit()
    db.refresh(jr)
    return stringify_ids(jr)


def update_job_requirement(
    db: Session, jr_id: int, payload: Dict[str, Any], user_id: int, user_role: str
):
    is_hr_personnel = str(user_id) in HR_USER_IDS

    if user_role == "executive" and not is_hr_personnel:
        raise HTTPException(status_code=401, detail="Unauthorized Access")

    jr = db.query(JobRequirement).filter(JobRequirement.id == jr_id).first()
    if not jr:
        raise HTTPException(status_code=404, detail="Job Requirement not found")

    # Workflow Gate: Ensure only the designated Approver or Super Admin can shift status to approved/rejected
    if "status" in payload and payload["status"] in ["approved", "rejected"]:
        is_approver = str(user_id) == str(jr.approver_id)
        is_creator = str(user_id) == str(jr.created_by_id)
        # ONLY super_admin has true structural authorization, but let's match your exact hierarchy checks safely:
        if not (is_approver or is_creator) and user_role not in [
            "super_admin",
            "admin",
            "manager",
        ]:
            raise HTTPException(
                status_code=403,
                detail="Only the designated Approver or Creator can modify the workflow path.",
            )

    # General modification permission checks
    if (
        user_id not in [jr.created_by_id, jr.approver_id, jr.assignee_id]
        and user_role not in ["super_admin", "admin", "manager"]
        and not is_hr_personnel
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to modify this requirement",
        )

    for rel in ["approver", "assignee", "created_by", "submitted_by_user"]:
        payload.pop(rel, None)

    for key, value in payload.items():
        if hasattr(jr, key):
            setattr(jr, key, None if value == "" else value)

    try:
        db.commit()
        db.refresh(jr)
        return stringify_ids(jr)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


def get_all_job_requirements(
    request: Request,
    db: Session,
    mongodb,
    page: int = 1,
    jr_id: Optional[int] = None,
    hiring_position: Optional[str] = None,
    department: Optional[str] = None,
    hiring_location_city: Optional[str] = None,
    tentative_joining_date: Optional[str] = None,
    position_type: Optional[str] = None,
    business_vertical: Optional[str] = None,
):
    limit = 30
    offset = (page - 1) * limit
    filters = []
    single_id_request = False

    # 1. Detail View (Fetch by ID)
    if jr_id is not None:
        filters.append(JobRequirement.id == jr_id)
        single_id_request = True

    if hiring_position:
        filters.append(JobRequirement.hiring_position == hiring_position.strip())
    if business_vertical:
        filters.append(JobRequirement.business_vertical == business_vertical.strip())
    if position_type:
        filters.append(JobRequirement.position_type == position_type.strip())
    if department:
        filters.append(JobRequirement.department == department.strip())
    if hiring_location_city:
        filters.append(JobRequirement.hiring_location_city.ilike(f"%{hiring_location_city.strip()}%"))
    if tentative_joining_date:
        filters.append(JobRequirement.tentative_joining_date <= tentative_joining_date)

    if single_id_request:
        base_query = (
            db.query(JobRequirement).filter(and_(*filters))
            if filters
            else db.query(JobRequirement)
        )
        total_data_size = base_query.count()
        data = (
            base_query.offset(offset)
            .options(
                selectinload(JobRequirement.approver),
                selectinload(JobRequirement.assignee),
                selectinload(JobRequirement.created_by),
            )
            .limit(limit)
            .all()
        )

        serialized_data = []
        if len(data) != 0:
            jr: JobRequirement = data[0]
            note_pairs = []

            # ── FIX: SUPPORT BOTH STRUCTURAL BLUEPRINTS FOR JR NOTES ──
            # Look for notes stored cleanly as a flat string AND notes saved inside an object mapping wrapper
            note_pairs.append({"Parent_Id": str(jr.id), "module": "Job_Requirements"})
            note_pairs.append(
                {"Parent_Id.id": str(jr.id), "module": "Job_Requirements"}
            )

            # Bubble-up System: Query child candidate records linked to this JR
            child_candidates = (
                db.query(Candidate.id)
                .filter(Candidate.job_requirement_id == jr.id)
                .all()
            )
            for candidate in child_candidates:
                # ── FIX: SUPPORT BOTH STRUCTURAL BLUEPRINTS FOR CANDIDATE BUBBLE UP ──
                note_pairs.append(
                    {"Parent_Id": str(candidate.id), "module": "Candidates"}
                )
                note_pairs.append(
                    {"Parent_Id.id": str(candidate.id), "module": "Candidates"}
                )

            # Fetch combined notes array from MongoDB Notes collection system
            notes = get_notes(
                pair_filters=note_pairs, notes_collection=mongodb["Notes"]
            )

            # Manually append the MongoDB notes list right into the base entity dict layout
            jr_dict = stringify_ids(jr)
            jr_dict["notes"] = notes
            serialized_data.append(jr_dict)

        return {
            "data": serialized_data,
            "page_info": {"page": page, "total_pages": 1, "data_size": total_data_size},
        }

    else:
        # 2. Kanban/Summary Board Standard response
        query = (
            db.query(JobRequirement).filter(and_(*filters))
            if filters
            else db.query(JobRequirement)
        )
        total_data_size = query.count()
        data_records = (
            query.order_by(JobRequirement.created_time.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "data": stringify_ids(data_records),
            "page_info": {
                "page": page,
                "total_pages": math.ceil(total_data_size / limit)
                if total_data_size
                else 1,
                "data_size": total_data_size,
            },
        }


def delete_job_requirement(db: Session, jr_id: int, user_id: int, user_role: str):
    jr = db.query(JobRequirement).filter(JobRequirement.id == jr_id).first()
    if not jr:
        raise HTTPException(status_code=404, detail="Job Requirement not found")
    db.delete(jr)
    db.commit()
    return {"message": "deleted"}


# ── Candidate ────────────────────────────────────────────────────


def create_candidate(db: Session, data: Dict[str, Any], user_id: int, user_role: str):
    is_hr_personnel = str(user_id) in HR_USER_IDS

    if user_role == "executive" and not is_hr_personnel:
        raise HTTPException(status_code=401, detail="Unauthorized Access")

    # Map frontend keys to matching SQLAlchemy database columns
    if "jr_id" in data:
        data["job_requirement_id"] = data.pop("jr_id")
    if "assignee_owner" in data:
        data["assignee_id"] = data.pop("assignee_owner")
    if "work_experience_duration" in data:
        data["work_experience"] = data.pop("work_experience_duration")

    # Validation Checks
    if not data.get("candidate_name") or not data.get("job_requirement_id"):
        raise HTTPException(
            status_code=400, detail="candidate_name and job_requirement_id are required"
        )

    try:
        jr_id_int = int(data["job_requirement_id"])
        data["job_requirement_id"] = jr_id_int
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid job_requirement_id format")

    if data.get("assignee_id"):
        try:
            data["assignee_id"] = int(data["assignee_id"])
        except (ValueError, TypeError):
            data["assignee_id"] = None

    jr_exists = (
        db.query(JobRequirement.id).filter(JobRequirement.id == jr_id_int).first()
    )
    if not jr_exists:
        raise HTTPException(
            status_code=404, detail="Target Job Requirement parent does not exist"
        )

    candidate = Candidate(**data, created_by_id=user_id)
    try:
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        return stringify_ids(candidate)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")


def get_all_candidates(
    request: Request,
    db: Session,
    mongodb,
    page: int,
    candidate_id: Optional[int] = None,
    candidate_name: Optional[str] = None,
    candidate_status: Optional[str] = None,
    location_city: Optional[str] = None,
    industry: Optional[str] = None,
    assignee_id: Optional[int] = None,
    job_requirement_id: Optional[int] = None,
):
    limit = 30
    offset = (page - 1) * limit
    filters = []
    single_id_request = False

    if candidate_id is not None:
        filters.append(Candidate.id == candidate_id)
        single_id_request = True

    if candidate_name:
        filters.append(Candidate.candidate_name.ilike(f"%{candidate_name.strip()}%"))
    if candidate_status:
        filters.append(Candidate.candidate_status == candidate_status.strip())
    if location_city:
        filters.append(Candidate.location_city.ilike(f"%{location_city.strip()}%"))
    if industry:
        filters.append(Candidate.industry == industry.strip())
    if assignee_id:
        filters.append(Candidate.assignee_id == assignee_id)
    if job_requirement_id:
        filters.append(Candidate.job_requirement_id == job_requirement_id)

    if single_id_request:
        base_query = (
            db.query(Candidate).filter(and_(*filters))
            if filters
            else db.query(Candidate)
        )
        total_data_size = base_query.count()
        data = (
            base_query.offset(offset)
            .options(
                selectinload(Candidate.assignee),
                selectinload(Candidate.created_by),
                selectinload(Candidate.submitted_by_user),
            )
            .limit(limit)
            .all()
        )
        if not data:
            raise HTTPException(status_code=404, detail="Candidate not found")

        candidate = data[0]
        note_pairs = []

        # ── FIX: SUPPORT BOTH STRUCTURAL BLUEPRINTS FOR CANDIDATE ONLY NOTES ──
        note_pairs.append({"Parent_Id": str(candidate.id), "module": "Candidates"})
        note_pairs.append({"Parent_Id.id": str(candidate.id), "module": "Candidates"})

        notes = get_notes(pair_filters=note_pairs, notes_collection=mongodb["Notes"])

        candidate_dict = stringify_ids(candidate)
        candidate_dict["notes"] = notes

        return {
            "data": [candidate_dict],
            "page_info": {"page": 1, "total_pages": 1, "data_size": total_data_size},
        }

    else:
        base_query = (
            db.query(Candidate).filter(and_(*filters))
            if filters
            else db.query(Candidate)
        )
        total_data_size = base_query.count()
        data_records = (
            base_query.order_by(Candidate.created_time.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return {
            "data": stringify_ids(data_records),
            "page_info": {
                "page": page,
                "total_pages": math.ceil(total_data_size / limit)
                if total_data_size
                else 1,
                "data_size": total_data_size,
            },
        }


def update_candidate(
    db: Session,
    candidate_id: int,
    payload: Dict[str, Any],
    user_id: int,
    user_role: str,
):
    is_hr_personnel = str(user_id) in HR_USER_IDS
    if user_role == "executive" and not is_hr_personnel:
        raise HTTPException(status_code=401, detail="Unauthorized Access")

    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if "jr_id" in payload:
        payload["job_requirement_id"] = payload.pop("jr_id")
    if "assignee_owner" in payload:
        payload["assignee_id"] = payload.pop("assignee_owner")
    if "work_experience_duration" in payload:
        payload["work_experience"] = payload.pop("work_experience_duration")
    if "candidate_status" in payload:
        new_status = payload["candidate_status"]
        if new_status and str(new_status) != str(candidate.candidate_status):
            candidate.status_date = datetime.now(timezone.utc)

    payload.pop("status_date", None)

    for key, value in payload.items():
        if hasattr(candidate, key):
            if key in ["job_requirement_id", "assignee_id"] and value:
                try:
                    setattr(candidate, key, int(value))
                except (ValueError, TypeError):
                    pass
            else:
                setattr(candidate, key, None if value == "" else value)

    try:
        db.commit()
        db.refresh(candidate)
        return stringify_ids(candidate)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")


def delete_candidate(db: Session, candidate_id: int, user_id: int, user_role: str):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    db.delete(candidate)
    db.commit()
    return {"message": "deleted"}
