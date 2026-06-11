from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session
from typing import Optional
from ..database import get_db
from ..controllers import export_csv as repo
from ..models.deal import Deal  

export_csv_router = APIRouter(prefix="/export", tags=["export"])


@export_csv_router.get("/accounts")
def export_accounts_csv(
    request: Request,
    db: Session = Depends(get_db),
    account_name: Optional[str] = None,
    account_status: list[str] | None = Query(default=None),
    account_stage: Optional[str] = None,
    source: list[str] | None = Query(default=None),
    industry: list[str] | None = Query(default=None),
    city: Optional[str] = None,
    state: Optional[str] = None,
    phone: Optional[str] = None,
    account_owner_id: list[int] | None = Query(default=None),
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
    lender_name: list[str] | None = Query(default=None),
    case_status: list[str] | None = Query(default=None),
    ticket_login: list[str] | None = Query(default=None),
    loan_type: list[str] | None = Query(default=None),
    type_of_case_login: list[str] | None = Query(default=None),
    deal_owner_id: list[int] | None = Query(default=None),
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