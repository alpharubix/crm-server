from sqlalchemy import (BigInteger, Column, Date, Integer, Numeric, String, Text, DateTime, func, ForeignKey, BIGINT)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from ..database import Base

class Ticket(Base):
    __tablename__ = "tickets_merged"
    
    # Primary Key & Relationships
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(Integer, default=1, nullable=True, index=True)
    deal_id = Column(BigInteger, ForeignKey("deals_merged.id"), nullable=False)
    deal = relationship("Deal", back_populates="tickets")
    account_id = Column(BIGINT, ForeignKey("accounts_merged.id"), index=True)
    account = relationship("Account", back_populates="tickets")

    # Ticket Information
    loan_account_status = Column(String(100))
    ticket_login = Column(String(100))
    lender_name = Column(String(150))
    potential = Column(Numeric(15, 2))
    lender_login_type = Column(String(100))
    lender_login_date = Column(Date)
    partner_name = Column(String(150), nullable=True)
    targeted_disbursement_date = Column(Date)
    type_of_loan = Column(String(150))
    disbursement_date = Column(Date)
    ticket_status = Column(String(50))
    ticket_stage = Column(String(50))
    ticket_name = Column(String, nullable=True, index=True)  # Auto-generated: {deal_name}/T{seq}

    # Funding & Commercials
    approved_amount = Column(Numeric(15, 2))
    sanction_amount = Column(Numeric(15, 2))
    processing_fees = Column(Numeric(15, 2))
    disbursed_amount = Column(Numeric(15, 2))
    pf_percentage = Column(Numeric(8, 2))
    tenure = Column(Integer)
    insurance_amount = Column(Numeric(15, 2))
    loan_start_date = Column(Date)
    rate_of_interest = Column(Numeric(8, 2))
    loan_end_date = Column(Date)
    interest_type = Column(String(50))

    # Rejection Status
    lender_rejection_reason = Column(JSONB) # Multi-select picklist
    lender_rejection_status_explanation = Column(Text)
    customer_rejection_reason = Column(String(150), nullable=True)
    customer_rejection_status_explanation = Column(Text, nullable=True)

    # Audit & Tracking
    created_by = Column(BigInteger)
    modified_by = Column(BigInteger)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    @hybrid_property
    def modified_time(self):
        return self.updated_at

    @hybrid_property
    def modified_at(self):
        return self.updated_at