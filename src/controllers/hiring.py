import logging
import math
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy import and_
from sqlalchemy.orm import Session, selectinload
from starlette.requests import Request

from src.controllers.audit_log import log_action
from src.controllers.notes import get_notes
from src.models.hiring import Candidate, JobRequirement

# ── Job Requirement ──────────────────────────────────────────────


def stringify_ids(data):
    if isinstance(data, list):
        return [stringify_ids(item) for item in data]
    if hasattr(data, "__dict__"):  # For SQLAlchemy objects
        data = {c.name: getattr(data, c.name) for c in data.__table__.columns}
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


def create_job_requirement(
    db: Session, data: Dict[str, Any], user_id: int, user_role: str
):
    jr = JobRequirement(**data, created_by_id=user_id)
    db.add(jr)
    db.commit()
    db.refresh(jr)
    log_action(db, user_id, user_role, "CREATED", "JobRequirement", jr.id, data)
    return jr


def get_all_job_requirements(
    request: Request,
    db: Session,
    mongodb,
    page: int = 1, # Added default
    jr_id: Optional[int] = None,
    hiring_position: Optional[str] = None,
    department: Optional[str] = None,
    hiring_location_city: Optional[str] = None,
    tentative_joining_date: Optional[str] = None,
):
    limit = 30
    offset = (page - 1) * limit
    filters = []

    # 1. Single ID Fetch (This is what your Frontend is calling)
    if jr_id is not None:
        jr = (
            db.query(JobRequirement)
            .filter(JobRequirement.id == jr_id)
            .options(
                selectinload(JobRequirement.approver),
                selectinload(JobRequirement.assignee),
                selectinload(JobRequirement.created_by),
                # selectinload(JobRequirement.candidates), # Ensure this exists in model or remove
            )
            .first()
        )
        
        if not jr:
            raise HTTPException(status_code=404, detail="Job Requirement not found")

        # Fetch notes from MongoDB for this specific JR
        try:
            notes = get_notes(
                id_list=[str(jr.id)],
                notes_collection=mongodb["Notes"],
                module_name=["JobRequirement"],
            )
            jr.notes = notes
        except Exception:
            jr.notes = [] # Fallback if Mongo fails

        # IMPORTANT: Return in the exact same structure as the list view 
        # so the frontend data?.data?.[0] works correctly.
        return {
            "data": stringify_ids([jr]), # Wrap in a list
            "page_info": {"page": 1, "total_pages": 1, "data_size": 1},
        }

    # 2. List Fetch with Filters
    if hiring_position:
        filters.append(JobRequirement.hiring_position.ilike(f"%{hiring_position.strip()}%"))
    if department:
        filters.append(JobRequirement.department.ilike(f"%{department.strip()}%"))
    if hiring_location_city:
        filters.append(JobRequirement.hiring_location_city.ilike(f"%{hiring_location_city.strip()}%"))
    if tentative_joining_date:
        filters.append(JobRequirement.tentative_joining_date <= tentative_joining_date)

    base_query = db.query(JobRequirement).filter(and_(*filters)) if filters else db.query(JobRequirement)
    
    total = base_query.count()
    data = base_query.offset(offset).limit(limit).all()

    return {
        "data": stringify_ids(data),
        "page_info": {
            "page": page,
            "total_pages": math.ceil(total / limit) if total else 1,
            "data_size": total,
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
        log_action(db, user_id, user_role, "UPDATED", "JobRequirement", jr_id, payload)
        return jr
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")


def delete_job_requirement(db: Session, jr_id: int, user_id: int, user_role: str):
    jr = db.query(JobRequirement).filter(JobRequirement.id == jr_id).first()
    if not jr:
        raise HTTPException(status_code=404, detail="Job Requirement not found")
    db.delete(jr)
    db.commit()
    log_action(db, user_id, user_role, "DELETED", "JobRequirement", jr_id, {})
    return {"message": "deleted"}


# ── Candidate ────────────────────────────────────────────────────


def create_candidate(db: Session, data: Dict[str, Any], user_id: int, user_role: str):
    # Remove job_requirement_id from the data if it accidentally comes from frontend
    # data.pop("job_requirement_id", None)

    # Create the candidate instance
    candidate = Candidate(**data, created_by_id=user_id)

    try:
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        # Log the action
        log_action(db, user_id, user_role, "CREATED", "Candidate", candidate.id, data)

        # Stringify IDs for JS precision safety
        return stringify_ids(candidate)

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")


# src/controllers/hiring.py


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

    # 1. Single ID Fetch
    if candidate_id is not None:
        candidate = (
            db.query(Candidate)
            .filter(Candidate.id == candidate_id)
            .options(
                selectinload(Candidate.assignee),
                selectinload(Candidate.created_by),
                # job_requirement relationship removed
            )
            .first()
        )
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        candidate.notes = get_notes(
            id_list=[str(candidate.id)],
            notes_collection=mongodb["Notes"],
            module_name=["Candidate"],
        )
        return {
            "data": stringify_ids([candidate]),
            "page_info": {"page": 1, "total_pages": 1, "data_size": 1},
        }

    # 2. List Fetch with Filters (job_requirement_id removed)
    if candidate_name:
        filters.append(Candidate.candidate_name.ilike(f"%{candidate_name.strip()}%"))
    if candidate_status:
        filters.append(Candidate.candidate_status == candidate_status)
    if location_city:
        filters.append(Candidate.location_city.ilike(f"%{location_city.strip()}%"))
    if industry:
        filters.append(Candidate.industry == industry)
    if assignee_id:
        filters.append(Candidate.assignee_id == assignee_id)
    if job_requirement_id:
        filters.append(Candidate.job_requirement_id == job_requirement_id)

    base_query = (
        db.query(Candidate).filter(and_(*filters)) if filters else db.query(Candidate)
    )
    total = base_query.count()
    data = base_query.offset(offset).limit(limit).all()

    return {
        "data": stringify_ids(data),
        "page_info": {
            "page": page,
            "total_pages": math.ceil(total / limit) if total else 1,
            "data_size": total,
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
        log_action(
            db, user_id, user_role, "UPDATED", "Candidate", candidate_id, payload
        )
        return candidate
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")


def delete_candidate(db: Session, candidate_id: int, user_id: int, user_role: str):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    db.delete(candidate)
    db.commit()
    log_action(db, user_id, user_role, "DELETED", "Candidate", candidate_id, {})
    return {"message": "deleted"}
