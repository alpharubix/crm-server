from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas.contact import  ContactCreate, ContactResponse
from ..controllers import account as repo

router = APIRouter(prefix="/contacts", tags=["contacts"])

@router.post("/", response_model=ContactResponse)
def create(data: ContactCreate, db: Session = Depends(get_db)):
    return repo.create_account(db, data)


@router.get("/", response_model=ContactResponse)
def list_all(page:int=1,name:str='',phone:str='',company_name:str='',db: Session = Depends(get_db)):
    return repo.get_all_accounts(db,page,name,phone,company_name)

# @router.get("/{contact_id}", response_model=AccountResponse)
# def get_by_id(contact_id: int, db: Session = Depends(get_db)):
#     return repo.get_contact_by_id(db, contact_id)