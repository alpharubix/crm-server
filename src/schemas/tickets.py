from typing import Optional, List, Any
from pydantic import BaseModel
from datetime import datetime, date

class TicketCreationBody(BaseModel):
    deal_id: int
    loan_account_status: Optional[str] = None
    ticket_login: Optional[str] = None
    lender_name: Optional[str] = None
    potential: Optional[float] = None
    lender_login_type: Optional[str] = None
    lender_login_date: Optional[date] = None
    partner_code: Optional[str] = None
    targeted_disbursement_date: Optional[date] = None
    type_of_loan: Optional[str] = None
    disbursement_date: Optional[date] = None
    ticket_status: Optional[str] = None
    ticket_stage: Optional[str] = None
    approved_amount: Optional[float] = None
    sanction_amount: Optional[float] = None
    processing_fees: Optional[float] = None
    disbursed_amount: Optional[float] = None
    pf_percentage: Optional[float] = None
    tenure: Optional[int] = None
    insurance_amount: Optional[float] = None
    loan_start_date: Optional[date] = None
    rate_of_interest: Optional[float] = None
    loan_end_date: Optional[date] = None
    interest_type: Optional[str] = None
    account_id: Optional[str] = None
    customer_rejection_reason: Optional[str] = None
    customer_rejection_status_explanation: Optional[str] = None

class TicketSchema(TicketCreationBody):
    id: int
    lender_rejection_reason: Optional[Any] = None
    lender_rejection_status_explanation: Optional[str] = None
    created_by: Optional[int] = None
    modified_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TicketListResponse(BaseModel):
    data: List[TicketSchema]
    page_info: dict