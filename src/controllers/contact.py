import math
from fastapi import HTTPException
from sqlalchemy import and_,or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, session
from starlette.requests import Request

from ..models.contact import Contact
from ..schemas.contact import ContactBase


def create_contact(db: Session, data: ContactBase):
    new_contact = Contact(
        id=data.id,
        account_id=data.account_id,  # Link to Account
        owner_id=data.owner_id,
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
        custom_fields=data.custom_fields,
    )

    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)
    return new_contact


def get_all_contacts(
    request,  # Added request to access user state
    db: Session,
    page: int,
    contact_id: int | None = None,
    phone: str = None,
    mobile: str = None,
    city: str = "",
    email: str = "",
    full_name: str = "",
):
    # Same Map as in get_all_accounts
    MANAGER_EXECUTIVES_MAP = {
        3899927000000318361: [
            3899927000005965018,
            3899927000004429017,
            3899927000004808001,
            3899927000007673012,
            3899927000005114004,
            3899927000005114020,
            3899927000005965050,
        ],
        3899927000005114050: [
            3899927000005965018,
            3899927000004429017,
            3899927000004808001,
            3899927000007673012,
            3899927000005114004,
            3899927000005114020,
            3899927000005965050,
        ],
        3899927000005114004: [
            3899927000005965018,
            3899927000004429017,
            3899927000007673012,
        ],
        3899927000005114020: [
            3899927000004808001,
            3899927000005965018,
            3899927000007673012,
            3899927000005114004,
            3899927000004429017,
            3899927000005965050,
        ],
    }

    limit = 20
    offset = (page - 1) * limit
    query = db.query(Contact)
    filters = []

    # --- Role Based Logic Start ---
    user_id = request.state.user_id
    role = request.state.role
    allowed_owner_ids = None

    if role in ("super_admin", "admin"):
        pass  # No restrictions
    elif role == "manager":
        allowed_owner_ids = [user_id] + MANAGER_EXECUTIVES_MAP.get(user_id, [])
    elif role == "executive":
        allowed_owner_ids = [user_id]

    if allowed_owner_ids is not None:
        # Assuming the Contact model has a field 'contact_owner_id'
        # or similar relationship to determine ownership
        filters.append(Contact.owner_id.in_(allowed_owner_ids))
    # --- Role Based Logic End ---

    # Existing filters
    if contact_id:
        filters.append(Contact.id == contact_id)
    if city and city.strip():
        filters.append(Contact.city.ilike(f"%{city.strip()}%"))
    if email and email.strip():
        filters.append(Contact.email.ilike(f"%{email.strip()}%"))
    if full_name and full_name.strip():
        filters.append(Contact.last_name.ilike(f"%{full_name.strip()}%"))
    if phone and phone.strip():
        filters.append(or_(Contact.mobile.startswith(phone), Contact.mobile.startswith(f'+91{phone}')))
    if mobile and mobile.strip():
        filters.append(or_(Contact.mobile.startswith(mobile),Contact.mobile.startswith(f'+91{mobile}')))
    base_query = query.filter(and_(*filters)) if filters else query

    total_data_size = base_query.count()
    data = (
        base_query.offset(offset)
        .options(
            joinedload(Contact.parent_account),
            joinedload(Contact.contact_owner),
            joinedload(Contact.created_by),
            joinedload(Contact.modified_by),
        )
        .limit(limit)
        .all()
    )
    total_pages = math.ceil(total_data_size / limit)

    return {
        "data": data,
        "page_info": {
            "page": page,
            "total_pages": total_pages,
            "data_size": total_data_size,
        },
    }

def update_contacts(request:Request,contact_id:int,body:dict,db:session):
    try:
        contact = db.query(Contact).filter(Contact.id == contact_id).first()

        if not contact:
            raise HTTPException(status_code=404, detail=({"msg":"No Contact found"}))
        else:
            for key,value in body.items():
                if value == '' or None:
                    setattr(contact, key, None)
                elif hasattr(contact,key):
                    setattr(contact, key, value)
            user_id = request.state.user_id
            setattr(contact,"modified_by_id",int(user_id))
            db.commit()
            db.refresh(contact)
            return {"message": "update-success", "updated_contact":contact}
    except HTTPException as e:
        raise e
    except Exception as e:
        print(e)
        db.rollback()
        raise HTTPException(status_code=500, detail=({"msg":"Internal server error"}))