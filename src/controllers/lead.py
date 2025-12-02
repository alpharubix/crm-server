from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from ..models.lead import Lead
from ..schemas.lead import LeadrCreate

def create_customer(db: Session, data: LeadrCreate) -> Lead:
    # 1. Check Logic
    if db.query(Lead).filter(Lead.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email exists")

    # 2. DB Operation
    new_customer = Lead(**data.model_dump())
    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)
    
    # 3. Return RAW SQLALCHEMY OBJECT
    return new_customer


def get_all_customers(db: Session):
    return db.query(Lead).all()

