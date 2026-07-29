from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, EmailStr


class InvoiceMaster(BaseModel):
    # Processing Details
    anchor: str
    processed_by: str
    working_date: date
    invoice_received_date: date
    received_time: time

    # Loan Details
    loan_type: str
    lender_name: str
    loan_amount: Decimal
    loan_disbursement_date: date
    aging: int
    tenure: int
    utr: str
    status: str
    status_reason: str

    # Distributor Details
    distributor_name: str
    distributor_code: int
    contact_number: str
    email_id: EmailStr
    himalaya_cfa: str

    # Beneficiary Bank Details
    beneficiary_name: str
    beneficiary_a_c_no: str
    bank_name: str
    ifsc_code: str
    branch: str

    # Invoice Details
    invoice_no: int
    invoice_amount: Decimal
    invoice_date: date
    comments: str

    # Audit Fields
    created_at: datetime
    updated_at: datetime
    created_by: int
    updated_by: int
