from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session
from starlette.requests import Request

from ..controllers import hiring as repo
from ..database import get_db, get_mongodb

jr_router = APIRouter(prefix="/job-requirements", tags=["job-requirements"])
candidate_router = APIRouter(prefix="/candidates", tags=["candidates"])


# ── Job Requirements ─────────────────────────────────────────────


@jr_router.post("/")
@jr_router.post("")
def create_job_requirement(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    user_id = int(request.state.user_id)
    user_role = request.state.role
    return repo.create_job_requirement(db, payload, user_id, user_role)


@jr_router.get("/")
@jr_router.get("")
def list_job_requirements(
    request: Request,
    page: int = 1,
    jr_id: Optional[int] = None,
    hiring_position: Optional[str] = None,
    department: Optional[str] = None,
    hiring_location_city: Optional[str] = None,
    tentative_joining_date: Optional[str] = None,
    db: Session = Depends(get_db),
    mongodb=Depends(get_mongodb),
    business_vertical: Optional[str] = None,
    position_type: Optional[str] = None,
):
    return repo.get_all_job_requirements(
        request=request,
        db=db,
        mongodb=mongodb,
        page=page,
        jr_id=jr_id,
        hiring_position=hiring_position,
        department=department,
        hiring_location_city=hiring_location_city,
        tentative_joining_date=tentative_joining_date,
        business_vertical=business_vertical,
        position_type=position_type
    )


@jr_router.put("/{jr_id}")
def update_job_requirement(
    request: Request,
    jr_id: int,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    user_id = int(request.state.user_id)
    user_role = request.state.role
    updated = repo.update_job_requirement(db, jr_id, payload, user_id, user_role)
    return {"message": "update-success", "updated": updated}


@jr_router.delete("/{jr_id}")
def delete_job_requirement(
    request: Request,
    jr_id: int,
    db: Session = Depends(get_db),
):
    user_id = int(request.state.user_id)
    user_role = request.state.role
    return repo.delete_job_requirement(db, jr_id, user_id, user_role)


# ── Candidates ───────────────────────────────────────────────────


@candidate_router.post("/")
@candidate_router.post("")
def create_candidate(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    user_id = int(request.state.user_id)
    user_role = request.state.role
    return repo.create_candidate(db, payload, user_id, user_role)


@candidate_router.get("/")
@candidate_router.get("")
def list_candidates(
    request: Request,
    page: int = 1,
    candidate_id: Optional[int] = None,
    job_requirement_id: Optional[int] = None,
    candidate_name: Optional[str] = None,
    candidate_status: Optional[str] = None,
    location_city: Optional[str] = None,
    industry: Optional[str] = None,
    assignee_id: Optional[int] = None,
    db: Session = Depends(get_db),
    mongodb=Depends(get_mongodb),
):
    return repo.get_all_candidates(
        request=request,
        db=db,
        mongodb=mongodb,
        page=page,
        candidate_id=candidate_id,
        job_requirement_id=job_requirement_id,
        candidate_name=candidate_name,
        candidate_status=candidate_status,
        location_city=location_city,
        industry=industry,
        assignee_id=assignee_id,
    )


@candidate_router.put("/{candidate_id}")
def update_candidate(
    request: Request,
    candidate_id: int,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    user_id = int(request.state.user_id)
    user_role = request.state.role
    updated = repo.update_candidate(db, candidate_id, payload, user_id, user_role)
    return {"message": "update-success", "updated": updated}


@candidate_router.delete("/{candidate_id}")
def delete_candidate(
    request: Request,
    candidate_id: int,
    db: Session = Depends(get_db),
):
    user_id = int(request.state.user_id)
    user_role = request.state.role
    return repo.delete_candidate(db, candidate_id, user_id, user_role)
