from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas.lead import LeadrCreate, LeadResponse
from ..controllers import lead as repo

router = APIRouter(prefix="/customers", tags=["customers"])

@router.post("/", response_model=LeadResponse)
def create(data: LeadrCreate, db: Session = Depends(get_db)):
    return repo.create_customer(db, data)


@router.get("/", response_model=list[LeadResponse])
def list_all(db: Session = Depends(get_db)):
    return repo.get_all_customers(db)

