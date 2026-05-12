from sqlalchemy import Column, Integer, Numeric, String, Text, DateTime, Date, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import BIGINT
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class Deal(Base):
    __tablename__ = "deals"

    # Primary Key
    id = Column(BIGINT, primary_key=True, autoincrement=True, index=True)

    # Foreign Keys
    account_id = Column(BIGINT, ForeignKey("accounts.id"), index=True)
    deal_owner_id = Column(BIGINT, ForeignKey("users.id"), index=True)

    # Relationships
    account = relationship("Account", back_populates="deals")
    owner = relationship("User", foreign_keys=[deal_owner_id], backref="deals")
    tickets = relationship("Ticket", back_populates="deal", cascade="all, delete-orphan")
    revenue = relationship(
        "Revenue",
        back_populates="deal",
        foreign_keys="Revenue.deal_id",
        cascade="all, delete-orphan"
    )
    # Deal & Ticket Info
    ticket_id = Column(BIGINT, index=True)
    ticket_number = Column(BIGINT)
    account_name = Column(String, nullable=True, index=True)
    deal_type = Column(String(100), nullable=True)
    loan_type = Column(String(150), nullable=True, index=True)
    type_of_login = Column(String(100), nullable=True)
    type_of_case_login = Column(String(100), nullable=True)
    ticket_login = Column(String(100), nullable=True)
    deal_stage = Column(String(50), nullable=True, index=True)
    deal_status = Column(String(50), nullable=True, index=True)
    crm_deal_id = Column(BIGINT, nullable=True, index=True)
    partner_code = Column(String(100), nullable=True)

    # Amounts
    disbursed_amount = Column(Numeric(15, 2), nullable=True)
    sanction_amount = Column(Numeric(15, 2), nullable=True)
    approved_amount = Column(Numeric(15, 2), nullable=True)
    amount_required = Column(Numeric(15, 2), nullable=False, server_default="0")
    processing_fees = Column(Numeric(15, 2), nullable=True)
    mm_charges = Column(Numeric(15, 2), nullable=True)
    insurance_amount = Column(Numeric(15, 2), nullable=True)
    pf_percentage = Column(Numeric(5, 2), nullable=True)
    rate_of_interest = Column(Numeric(5, 2), nullable=True)
    interest_type = Column(String(50), nullable=True)

    # Dates
    deal_call_back_datetime = Column(DateTime(timezone=True), nullable=True)
    disbursement_date = Column(Date, nullable=True)
    lender_login_date = Column(Date, nullable=True)
    loan_start_date = Column(Date, nullable=True)
    loan_end_date = Column(Date, nullable=True)
    targeted_disbursement_date = Column(Date, nullable=True)
    tenure = Column(Integer, nullable=True)

    # Lender
    lender_code = Column(String(100), nullable=True)
    lender_name = Column(String(150), nullable=True, index=True)
    lender_login_type = Column(String(100), nullable=True)

    # Rejection
    customer_rejection_reason = Column(String(150), nullable=True)
    customer_rejection_status_explanation = Column(Text, nullable=True)
    lender_rejection_reason = Column(String(150), nullable=True)
    lender_rejection_status_explanation = Column(Text, nullable=True)

    # Attachments
    payment_receipt = Column(JSONB, default=list, nullable=True)
    sanction_letter = Column(String, nullable=True)
    potential = Column(String(100), nullable=True)
    product = Column(String(100), nullable=True)
    deal_expected_closing = Column(Date, nullable=True)
    deal_status_closing = Column(Date, nullable=True)

    # Audit
    assignee_id = Column(BIGINT, nullable=True)
    created_by = Column(BIGINT, nullable=True)
    modified_by = Column(BIGINT, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Documentation
    documents = relationship("DealDocument", back_populates="deal", cascade="all, delete-orphan")