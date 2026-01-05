import math
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from ..models.contact import Contact
from ..schemas.contact import ContactBase

def create_contact(db: Session, data: ContactBase):
    # 1. Check if Email exists
    if db.query(Contact).filter(Contact.email == data.email).first():
        raise HTTPException(status_code=400, detail="Contact email already exists")

    # 2. Check if Account exists (Logic Check)
    # if data.account_id:
    #     if not db.query(Account).filter(Account.id == data.account_id).first():
    #         raise HTTPException(status_code=404, detail="Associated Account not found")

    # 3. Create
    new_contact = Contact(
        id=data.id,
        account_id=data.account_id,  # Link to Account
        owner_id = data.owner_id,
        modified_by_id=data.modified_by_id,
        created_by_id=data.created_by_id,
        created_time=data.created_time,
        modified_time=data.modified_time,
        first_name=data.first_name,
        last_name=data.last_name,
        designation=data.designation,
        email=data.email,
        secondary_email=data.secondary_email,
        mobile=data.mobile,
        phone=data.phone,
        lead_source=data.lead_source,
        street=data.street,
        city=data.city,
        state=data.state,
        country=data.country,
        pincode=data.pincode,
        custom_fields=data.custom_fields
    )

    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)
    return new_contact

def get_all_contacts(
    db: Session,
    page: int,
    account_id: int | None = None, # Filter by Account ID
    lead_source: str = "",
    city: str = "",
    email: str = ""
):
    limit = 10
    offset = (page - 1) * limit
    query = db.query(Contact)
    filters = []

    if account_id:
        filters.append(Contact.account_id == account_id)
    if lead_source:
        filters.append(Contact.lead_source == lead_source)
    if city:
        filters.append(Contact.city.ilike(f"{city}%"))
    if email:
        filters.append(Contact.email.ilike(f"{email}%"))

    base_query = query.filter(*filters) if filters else query
    total_data_size = base_query.with_entities(func.count(Contact.id)).scalar()
    data = base_query.offset(offset).limit(limit).all()
    total_pages = math.ceil(total_data_size / limit)

    return {
        "data": data,
        "page_info": {
            "page": page,
            "total_pages": total_pages,
            "data_size": total_data_size,
        },
    }