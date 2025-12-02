from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from ..models.contact import Contact
from ..schemas.lead import LeadrCreate

def create_customer(db: Session, data: ContactCreate) -> Contact:
    # 1. Check Logic
    if db.query(Contact).filter(Contact.email == data.email).first():
        raise HTTPException(status_code=400, detail="user is already exist")

    # 2. DB Operation
    customer_info = Contact(**data.model_dump())
    db.add(customer_info)
    db.commit()
    db.refresh(customer_info)
    
    # 3. Return RAW SQLALCHEMY OBJECT
    return customer_info


def get_all_customers(db: Session):
    return db.query(Contact).all()
