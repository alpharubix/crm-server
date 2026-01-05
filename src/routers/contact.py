from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas.contact import ContactResponseList,ContactBase
from ..controllers.contact import create_contact, get_all_contacts

router = APIRouter(prefix="/contacts", tags=["contacts"])

@router.post("/",)
def create(data: ContactBase, db: Session = Depends(get_db)):
    return create_contact(data=data, db=db)


@router.get("/",response_model=ContactResponseList)
def list_all(contact_id:int=None,page:int=1,first_name:str=None,last_name:str=None,email:str=None,city:str=None,db: Session = Depends(get_db)):
    return get_all_contacts(db,page,contact_id,city,email,first_name,last_name)