import math
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..models.account import Account
from ..schemas.account import AccountCreate

# def create_account(db: Session, data: AccountCreate) -> Account:
#     if db.query(Account).filter(Account.email == data.email).first():
#         raise HTTPException(status_code=400, detail="Email exists")

#     # Mapping Logic
#     new_account = Account(
#         # Map Schema 'name' -> Model 'full_name'
#         full_name=data.full_name,

#         # Direct Mappings
#         phone_number=data.phone_number,
#         email=data.email,
#         pan=data.pan,
#         gstin=data.gstin,

#         # Optional fields (will be None if not sent)
#         company=data.company,
#         annual_revenue=data.annual_revenue,
#         city=data.city,
#         industry=data.industry,
#         description=data.description
#     )

#     db.add(new_account)
#     db.commit()
#     db.refresh(new_account)
#     return new_account


# def get_all_accounts(db: Session,page:int,name:str,phone:str,company_name:str):#responsible for getting all the accounts with or without filter
#     print("Query parameters",page,name,phone,company_name)
#     limit = 10
#     offset = (page-1)*limit
#     query  =  db.query(Account)
#     filter = []
#     if name:
#         filter.append(Account.full_name.ilike(f"{name}%"))
#     if phone:
#         filter.append(Account.phone_number.ilike(f"{phone}%"))
#     if company_name:
#         filter.append(Account.company.ilike(f"{company_name}%"))
#     base_query = query.filter(*filter)
#     total_data_size = base_query.count()
#     print("total data length",total_data_size)
#     data = (
#         base_query
#         .offset(offset)
#         .limit(limit)
#         .all()
#     )
#     total_pages = math.ceil(total_data_size / limit)
#     return {"data":data,"page_info":{"page":page,"total_pages":total_pages,"data_size":total_data_size}}


# def update_customer(db: Session, account_id: int, data: AccountCreate) -> Account:
#     # 1. Find the account
#     account = db.query(Account).filter(Account.id == account_id).first()
#     if not account:
#         raise HTTPException(status_code=404, detail="Account not found")

#     # 2. Update fields safely
#     account_data = data.model_dump(exclude_unset=True) # Only get sent fields
#     for key, value in account_data.items():
#         setattr(Account, key, value)

#     # 3. Save
#     db.commit()
#     db.refresh(Account)
#     return account

# def get_account_by_id(db: Session, account_id: int):
#     return db.query(Account).filter(Account.id == account_id).first()


def create_account(db: Session, data: AccountCreate, created_by: str = "") -> Account:
    if db.query(Account).filter(Account.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email exists")

    new_account = Account(
        id=data.id,
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        phone=data.phone,
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
    db: Session,
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
        )  # Or use date range
    print(filters)
    base_query = query.filter(*filters) if filters else query
    total_data_size = base_query.with_entities(func.count(Account.id)).scalar()
    data = base_query.offset(offset).options(joinedload(Account.owner),joinedload(Account.created_by)).limit(limit).all()
    total_pages = math.ceil(total_data_size / limit)

    return {
        "data": data,
        "page_info": {
            "page": page,
            "total_pages": total_pages,
            "data_size": total_data_size,
        },
    }


def update_account(
    db: Session, account_id: int, data: AccountCreate, modified_by: str = ""
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

    # def convert_account_to_account(db: Session, lead_id: int):
    # 1. Validation: Does the Lead exist?
    lead = db.query(Account).filter(Account.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if lead.business_status == "Converted":
        raise HTTPException(status_code=400, detail="Lead is already converted")

    try:
        # 2. Create ACCOUNT (The Business Entity)
        # Logic: If 'company' exists, use it. Otherwise, use the Person's Name.
        account_name = lead.company if lead.company else f"{lead.full_name}'s Account"

        new_account = Account(name=account_name, industry=lead.industry, city=lead.city)
        db.add(new_account)
        db.flush()  # CRITICAL: This generates the 'new_account.id' without finishing the transaction yet

        # 3. Create CONTACT (The Person)
        # Link it to the new_account.id we just generated
        new_contact = Contact(
            account_id=new_account.id,
            # first_name=lead.full_name.split(" ")[0] if lead.full_name else "",
            # last_name=lead.full_name.split(" ")[-1] if lead.full_name and " " in lead.full_name else "",
            full_name=lead.full_name,
            email=lead.email,
            phone=lead.phone_number,
        )
        db.add(new_contact)

        # 4. Update LEAD Status (Archive it)
        lead.business_status = "Converted"

        # 5. Commit Everything
        db.commit()
        db.refresh(new_account)

        return {
            "status": "success",
            "message": "Lead converted successfully",
            "account_id": new_account.id,
            "contact_id": new_contact.id,
        }

    except Exception as e:
        db.rollback()  # Safety Net: If Contact fails, undo the Account creation too
        raise HTTPException(status_code=500, detail=str(e))
