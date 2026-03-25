from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from ..controllers import export_csv as repo
from ..models.deal import Deal  
from ..database import get_mongodb

export_csv_router = APIRouter(prefix="/export", tags=["export"])


@export_csv_router.get("/accounts")
def export_accounts_csv(
    request: Request,
    db: Session = Depends(get_db),
    account_name: Optional[str] = None,
    account_status: Optional[str] = None,
    account_stage: Optional[str] = None,
    source: Optional[str] = None,
    industry: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    phone: Optional[str] = None,
    account_owner_id: Optional[int] = None,
    call_back_date_time: Optional[str] = None,
):
    return repo.export_accounts_csv(
        request=request,
        db=db,
        account_name=account_name,
        account_status=account_status,
        account_stage=account_stage,
        source=source,
        industry=industry,
        city=city,
        state=state,
        phone_number=phone,
        account_owner_id=account_owner_id,
        call_back_date_time=call_back_date_time,
    )


# deals export 
@export_csv_router.get("/deals")
def export_deals(
    request: Request,
    db: Session = Depends(get_db),
    account_name: Optional[str] = None,
    lender_name: Optional[str] = None,
    case_status: Optional[str] = None,
    ticket_login: Optional[str] = None,
    loan_type: Optional[str] = None,
    type_of_case_login: Optional[str] = None,
    deal_owner_id: Optional[int] = None,
):
    return repo.export_deals_csv(
        request=request,
        db=db,
        account_name=account_name,
        lender_name=lender_name,
        case_status=case_status,
        ticket_login=ticket_login,
        loan_type=loan_type,
        type_of_case_login=type_of_case_login,
        deal_owner_id=deal_owner_id,
    )

@export_csv_router.get("/contacts")
def export_contacts(
    request: Request,
    db: Session = Depends(get_db),
    phone: Optional[str] = None,
    mobile: Optional[str] = None,
    city: Optional[str] = None,
    email: Optional[str] = None,
    full_name: Optional[str] = None,
):
    return repo.export_contacts_csv(
        request=request,
        db=db,
        phone=phone,
        mobile=mobile,
        city=city,
        email=email,
        full_name=full_name,
       
    )


@export_csv_router.get("/notes")
def export_notes(
    request: Request,
    mongodb=Depends(get_mongodb),
    module: Optional[str] = None,
    parent_id: Optional[str] = None,
    owner_id: Optional[str] = None,
    created_from: Optional[str] = None,
    created_to: Optional[str] = None,
):
    return repo.export_notes_csv(
        request=request,
        mongodb=mongodb,
        module=module,
        parent_id=parent_id,
        owner_id=owner_id,
        created_from=created_from,
        created_to=created_to,
    )