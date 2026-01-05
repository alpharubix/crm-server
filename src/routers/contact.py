from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas.contact import ContactBase
from ..controllers.contact import create_contact, get_all_contacts

router = APIRouter(prefix="/contacts", tags=["contacts"])

@router.post("/",)
def create(data: ContactBase, db: Session = Depends(get_db)):
    return create_contact(data=data, db=db)


@router.get("/",)
def list_all(page:int=1,name:str='',phone:str='',company_name:str='',db: Session = Depends(get_db)):
    return get_all_contacts(db,page,name,phone,company_name)