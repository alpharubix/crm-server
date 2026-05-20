import logging
import math
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, selectinload
from starlette.requests import Request

# from src.controllers.audit_log import log_action
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
                    res[rel] = {"id": str(val.id), "name": getattr(val, "name", getattr(val, "username", str(val.id)))}
        return res
        
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

def create_job_requirement(
    db: Session, data: Dict[str, Any], user_id: int, user_role: str
):
    jr = JobRequirement(**data, created_by_id=user_id)
    db.add(jr)
    db.commit()
    db.refresh(jr)
    # log_action(db, user_id, user_role, "CREATED", "JobRequirement", jr.id, data)
    return stringify_ids(jr)


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
    if department:
        filters.append(JobRequirement.department == department.strip())
    if hiring_location_city:
        filters.append(JobRequirement.hiring_location_city == hiring_location_city.strip())
    if tentative_joining_date:
        filters.append(JobRequirement.tentative_joining_date <= tentative_joining_date)

    if single_id_request:
        base_query = db.query(JobRequirement).filter(and_(*filters)) if filters else db.query(JobRequirement)
        total_data_size = base_query.count()
        data = (
            base_query.offset(offset)
            .options(
                selectinload(JobRequirement.approver),
                selectinload(JobRequirement.assignee),
                selectinload(JobRequirement.created_by)
            )
            .limit(limit)
            .all()
        )
        
        if len(data) != 0:
            jr: JobRequirement = data[0]
            note_pairs = []
            
            # Match the pair_filters system from get_all_accounts
            note_pairs.append({"Parent_Id.id": str(jr.id), "module": "JobRequirement"})
            
            # Fetch paired notes dictionary from MongoDB
            jr.notes = get_notes(
                pair_filters=note_pairs,
                notes_collection=mongodb["Notes"]
            )
            
        return {"data": stringify_ids(data), "page_info": {"page": page, "total_pages": 1, "data_size": total_data_size}}

    else:
        # 2. Kanban/Summary Board Standard response
        query = db.query(JobRequirement).filter(and_(*filters)) if filters else db.query(JobRequirement)
        total_data_size = query.count()
        data_records = query.order_by(JobRequirement.created_time.desc()).offset(offset).limit(limit).all()

        return {
            "data": stringify_ids(data_records),
            "page_info": {
                "page": page,
                "total_pages": math.ceil(total_data_size / limit) if total_data_size else 1,
                "data_size": total_data_size,
            },
        }

def update_job_requirement(
    db: Session, jr_id: int, payload: Dict[str, Any], user_id: int, user_role: str
):
    jr = db.query(JobRequirement).filter(JobRequirement.id == jr_id).first()
    if not jr:
        raise HTTPException(status_code=404, detail="Job Requirement not found")

    for key, value in payload.items():
        if hasattr(jr, key):
            setattr(jr, key, None if value == "" else value)

    try:
        db.commit()
        db.refresh(jr)
        # log_action(db, user_id, user_role, "UPDATED", "JobRequirement", jr_id, payload)
        return stringify_ids(jr)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")


def delete_job_requirement(db: Session, jr_id: int, user_id: int, user_role: str):
    jr = db.query(JobRequirement).filter(JobRequirement.id == jr_id).first()
    if not jr:
        raise HTTPException(status_code=404, detail="Job Requirement not found")
    db.delete(jr)
    db.commit()
    # log_action(db, user_id, user_role, "DELETED", "JobRequirement", jr_id, {})
    return {"message": "deleted"}


# ── Candidate ────────────────────────────────────────────────────


def create_candidate(db: Session, data: Dict[str, Any], user_id: int, user_role: str):
    candidate = Candidate(**data, created_by_id=user_id)
    try:
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        # log_action(db, user_id, user_role, "CREATED", "Candidate", candidate.id, data)
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

    # 1. Single ID Fetch
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
        base_query = db.query(Candidate).filter(and_(*filters)) if filters else db.query(Candidate)
        total_data_size = base_query.count()
        data = (
            base_query.offset(offset)
            .options(
                selectinload(Candidate.assignee),
                selectinload(Candidate.created_by),
                selectinload(Candidate.submitted_by_user)
            )
            .limit(limit)
            .all()
        )
        if not data:
            raise HTTPException(status_code=404, detail="Candidate not found")

        candidate = data[0]
        note_pairs = []
        
        # Syncing with pair_filters format
        note_pairs.append({"Parent_Id.id": str(candidate.id), "module": "Candidate"})
        
        candidate.notes = get_notes(
            pair_filters=note_pairs,
            notes_collection=mongodb["Notes"]
        )
        return {
            "data": stringify_ids(data),
            "page_info": {"page": 1, "total_pages": 1, "data_size": total_data_size},
        }

    else:
        # Standard Kanban board view response
        base_query = db.query(Candidate).filter(and_(*filters)) if filters else db.query(Candidate)
        total_data_size = base_query.count()
        data_records = base_query.order_by(Candidate.created_time.desc()).offset(offset).limit(limit).all()

        return {
            "data": stringify_ids(data_records),
            "page_info": {
                "page": page,
                "total_pages": math.ceil(total_data_size / limit) if total_data_size else 1,
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
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    for key, value in payload.items():
        if hasattr(candidate, key):
            setattr(candidate, key, None if value == "" else value)

    try:
        db.commit()
        db.refresh(candidate)
        # log_action(db, user_id, user_role, "UPDATED", "Candidate", candidate_id, payload)
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
    # log_action(db, user_id, user_role, "DELETED", "Candidate", candidate_id, {})
    return {"message": "deleted"}