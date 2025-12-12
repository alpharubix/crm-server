from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas.lead import LeadCreate, LeadResponse
from ..controllers import lead as repo

router = APIRouter(prefix="/leads", tags=["leads"])

@router.post("/", response_model=LeadResponse)
def create(data: LeadCreate, db: Session = Depends(get_db)):
    return repo.create_lead(db, data)


@router.get("/", response_model=list[LeadResponse])
def list_all(db: Session = Depends(get_db)):
    return repo.get_all_leads(db)


@router.put("/{lead_id}", response_model=LeadResponse)
def update(lead_id: int, data: LeadCreate, db: Session = Depends(get_db)):
    return repo.update_customer(db, lead_id, data)


@router.post("/{lead_id}/convert")
def convert_lead(lead_id: int, db: Session = Depends(get_db)):
    """
    Transactions: 
    1. Creates Account
    2. Creates Contact linked to Account
    3. Marks Lead as 'Converted'
    """
    return repo.convert_lead_to_account(db, lead_id)