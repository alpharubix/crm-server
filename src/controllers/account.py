import math
from datetime import datetime
from fastapi import HTTPException
from pymongo.synchronous.collection import Collection
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload
from starlette.requests import Request
from ..models.account import Account
from ..schemas.account import  AccountBase

def create_account(db: Session, data: AccountBase, created_by: str = "") -> Account:
    if db.query(Account).filter(Account.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email exists")

    new_account = Account(
        id=data.id,
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        phone=data.phone,
        account_name=data.account_name,
        account_owner_id=data.account_owner_id,
        account_status=data.account_status,
        account_stage=data.account_stage,
        source=data.source,
        business_status=data.business_status,
        distributor_code=data.distributor_code,
        type_of_business=data.type_of_business,
        industry=data.industry,
        city=data.city,
        state=data.state,
        pincode=data.pincode,
        waba_interested=data.waba_interested,
        call_back_date_time=data.call_back_date_time,
        custom_fields=data.custom_fields,
        created_by_id=data.created_by_id,
        created_time=data.created_time,
        modified_time=data.modified_time,
    )

    db.add(new_account)
    db.commit()
    db.refresh(new_account)
    return new_account


def get_all_accounts(
    request: Request,
    db: Session,
    mongodb:Collection,
    page: int,
    account_id: int = "",
    account_status: str = "",
    source: str = "",
    type_of_business: str = "",
    industry: str = "",
    city: str = "",
    state: str = "",
    pincode: str = "",
    waba_interested: bool | None = None,
    business_status: str = "",
    call_back_date_time: str | datetime = "",
):
    limit = 10
    offset = (page - 1) * limit
    query = db.query(Account)
    filters = []
    notes=[]

    if account_id is not None:
        filters.append(Account.id == account_id)
    if account_status:
        filters.append(Account.account_status == account_status)
    if source:
        filters.append(Account.source == source)
    if type_of_business:
        filters.append(Account.type_of_business == type_of_business)
    if industry:
        filters.append(Account.industry == industry)
    if city:
        filters.append(Account.city.ilike(f"{city}%"))
    if state:
        filters.append(Account.state.ilike(f"{state}%"))
    if pincode:
        filters.append(Account.pincode == pincode)
    if waba_interested is not None:
        filters.append(Account.waba_interested == waba_interested)
    if business_status:
        filters.append(Account.business_status == business_status)
    if call_back_date_time:
        filters.append(
            Account.call_back_date_time >= call_back_date_time
        )  # Or use date rang
    base_query = query.filter(*filters) if filters else query
    total_data_size = base_query.with_entities(func.count(Account.id)).scalar()
    data = base_query.offset(offset).options(joinedload(Account.owner),joinedload(Account.created_by),selectinload(Account.account_linked_contact)).limit(limit).all()
    for acc in data:
        acc_id = acc.id
        coll_notes = mongodb.find({'parent_id':acc_id},{'_id':0,'note':1,'parent_id':1,"created_time":1,"modified_time":1})
        for note in coll_notes:
            note['parent_id'] = str(note['parent_id'])
            notes.append(note)
        acc.notes = notes
    total_pages = math.ceil(total_data_size / limit)
    return {
        "data": data,
        "page_info": {
            "page": page,
            "total_pages": total_pages,
            "data_size": total_data_size,
        },
    }


