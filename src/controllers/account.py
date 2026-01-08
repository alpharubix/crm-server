import math
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from pymongo.synchronous.collection import Collection
from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload, selectinload
from starlette.requests import Request

from src.controllers.notes import get_notes

from ..models.account import Account
from ..schemas.account import AccountBase


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
    mongodb: Collection,
    page: int,
    account_name: Optional[str] = None,
    account_id: Optional[int] = None,
    account_status: Optional[str] = None,
    account_stage: Optional[str] = None,
    source: Optional[str] = None,
    type_of_business: Optional[str] = None,
    industry: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    pincode: Optional[str] = None,
    waba_interested: Optional[bool] = None,
    business_status: Optional[str] = None,
    call_back_date_time: Optional[datetime] = None,
    account_owner_id: Optional[int] = None,
):
    # Temprorary
    MANAGER_EXECUTIVES_MAP = {
        # Namrata
        3899927000000318361: [
            3899927000005965018,  # Arjun
            3899927000004429017,  # Sandeep
            3899927000004808001,  # Ayush
            3899927000007673012,  # Honappa
            3899927000005114004,  # Manjunath
            3899927000005114020,  # Digamber
            3899927000005965050,  # Sahil
        ],
        # Sutapa Roy
        3899927000005114050: [
            3899927000005965018,  # Arjun
            3899927000004429017,  # Sandeep
            3899927000004808001,  # Ayush
            3899927000007673012,  # Honappa
            3899927000005114004,  # Manjunath
            3899927000005114020,  # Digamber
            3899927000005965050,  # Sahil
        ],
        # Manjunath
        3899927000005114004: [
            3899927000005965018,  # Arjun
            3899927000004429017,  # Sandeep
            3899927000007673012,  # Honappa
        ],
        # Digamber
        3899927000005114020: [
            3899927000004808001,  # Ayush
            3899927000005965018,  # Arjun
            3899927000007673012,  # Honappa
            3899927000005114004,  # Manjunath
            3899927000004429017,  # Sandeep
            3899927000005965050,  # Sahil
        ],
        # manager_id: [executive_ids]
    }

    limit = 30
    offset = (page - 1) * limit
    query = db.query(Account)
    filters = []
    user_id = request.state.user_id
    role = request.state.role

    allowed_owner_ids = None

    if role in ("super_admin", "admin"):
        pass  # no restriction

    elif role == "manager":
        allowed_owner_ids = [user_id] + MANAGER_EXECUTIVES_MAP.get(user_id, [])

    elif role == "executive":
        allowed_owner_ids = [user_id]

    # filters.append(Account.account_owner_id == request.state.user_id)
    if allowed_owner_ids is not None:
        filters.append(Account.account_owner_id.in_(allowed_owner_ids))

    if account_id is not None:
        filters.append(Account.id == account_id)
    if account_name:
        filters.append(Account.account_name.ilike(f"{account_name.strip()}%"))
    if account_status:
        filters.append(Account.account_status.ilike(f"{account_status.strip()}%"))
    if account_stage:
        filters.append(Account.account_stage.ilike(f"{account_stage.strip()}%"))
    if source:
        filters.append(Account.source.ilike(f"{source.strip()}%"))
    if type_of_business:
        filters.append(Account.type_of_business == type_of_business)
    if industry:
        filters.append(Account.industry == industry)
    if city:
        print("im executing")
        filters.append(Account.city.ilike(f"{city.strip()}%"))
    if state:
        print("im state")
        filters.append(Account.state.ilike(f"{state.strip()}%"))
    if pincode:
        filters.append(Account.pincode == pincode)
    if waba_interested is not None:
        filters.append(Account.waba_interested == waba_interested)
    if business_status:
        filters.append(Account.business_status == business_status)
    if call_back_date_time:
        filters.append(Account.call_back_date_time >= call_back_date_time)
    if account_owner_id:
        if user_id not in MANAGER_EXECUTIVES_MAP:
            raise HTTPException(status_code=401, detail={"msg": "ACCESS DENIED"})
        else:
            filters.append(Account.account_owner_id == int(account_owner_id))
    print(filters)
    base_query = query.filter(and_(*filters)) if filters else query
    total_data_size = base_query.count()
    data = (
        base_query.offset(offset)
        .options(
            joinedload(Account.owner),
            joinedload(Account.created_by),
            selectinload(Account.account_linked_contact),
        )
        .limit(limit)
        .all()
    )
    if len(data) != 0:
        account_ids = [acc.id for acc in data]
        accounts_notes = get_notes(acc_ids=account_ids, live_notes_collection=mongodb)

        for acc in data:
            acc.notes = accounts_notes.get(acc.id)
    total_pages = math.ceil(total_data_size / limit)

    return {
        "data": data,  # Return the clean dictionaries
        "page_info": {
            "page": page,
            "total_pages": total_pages,
            "data_size": total_data_size,
        },
    }


def update_account(
    db: Session, account_id: int, data: AccountBase, modified_by: str = ""
) -> Account:
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    account_data = data.model_dump(exclude_unset=True)
    for key, value in account_data.items():
        setattr(account, key, value)

    account.modified_by = modified_by  # type: ignore

    db.commit()
    db.refresh(account)
    return account


def get_account_by_id(db: Session, account_id: int) -> Account:
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account
