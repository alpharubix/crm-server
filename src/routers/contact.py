from typing import Dict, Any

from fastapi import APIRouter, Depends, Request
from fastapi.params import Body
from sqlalchemy.orm import Session

from ..controllers.contact import create_contact, get_all_contacts
from ..database import get_db
from ..schemas.contact import ContactBase, ContactResponseList

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.post("")
@router.post("/")
def create(data: ContactBase, db: Session = Depends(get_db)):
    return create_contact(data=data, db=db)


@router.get("", response_model=ContactResponseList)
@router.get("/", response_model=ContactResponseList)
def list_all(
    request: Request,
    contact_id: int = None,
    page: int = 1,
    full_name: str = None,
    email: str = None,
    city: str = None,
    db: Session = Depends(get_db),
):
    return get_all_contacts(
        request, db, page, contact_id, city, email,full_name
    )

# @router.put("/{contact_id}")
# @router.put("{contact_id}")
# def update_contact(body:Dict[str, Any] = Body(...), db: Session = Depends(get_db)):
