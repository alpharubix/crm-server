from sqlalchemy import (
    BIGINT,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Date,
)
from sqlalchemy.dialects.postgresql import JSONB

# models/account.py - Only the changes needed
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class Account(Base):
    __tablename__ = "accounts_merged"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    company_id = Column(Integer, default=1, nullable=True, index=True)

    # Identity & Contact (Core)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    email = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String, unique=False, nullable=False)
    account_name = Column(String, nullable=True, index=True)

    # Workflow & Assignment (Core - Filtered)
    account_owner_id = Column(
        BIGINT, ForeignKey("users.id"), nullable=False, index=True
    )
    account_status = Column(String, nullable=True, index=True)
    account_stage = Column(String, nullable=True, index=True)
    source = Column(String, nullable=True, index=True)
    business_status = Column(String, nullable=True, index=True)
    distributor_code = Column(String, nullable=True, index=True)

    # Business Details (Core - Filtered)
    type_of_business = Column(String, nullable=True, index=True)
    industry = Column(String, nullable=True, index=True)
    profile_type = Column(String, nullable=True, index=True)
    is_priority_account = Column(String, nullable=True, index=True)
    is_active = Column(String, default="no", server_default="no", nullable=True, index=True)

    # Location (Core - Filtered)
    city = Column(String, nullable=True, index=True)
    state = Column(String, nullable=True, index=True)
    pincode = Column(String, nullable=True, index=True)

    # Flags & Dates (Core - Filtered)
    waba_interested = Column(Boolean, default=False, index=True)
    call_back_date_time = Column(DateTime(timezone=True), nullable=True, index=True)

    # Flexible Fields (JSONB)
    custom_fields = Column(JSONB, default={}, nullable=False)

    # System Audit (Core)
    created_time = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    modified_time = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    assignment_date = Column(DateTime(timezone=False), nullable=True)

    tickets = relationship("Ticket", back_populates="account")

    # Self-referencing Foreign Keys
    created_by_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)
    created_by = relationship(
        "User", foreign_keys=[created_by_id], backref="user_created_by_id"
    )
    modified_by_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)
    modified_by = relationship(
        "User", foreign_keys=[modified_by_id], backref="account_modified_by"
    )
    owner = relationship(
        "User", foreign_keys=[account_owner_id], backref="account_owner"
    )
    deals = relationship("Deal", back_populates="account")

    # ========== NEW COLUMNS (Add these at the end) ==========
    source_type = Column(String, nullable=True, index=True)
    source_other = Column(Text, nullable=True)
    mothers_name = Column(String, nullable=True)
    preferred_languages = Column(JSONB, default=list)
    parent_account_id = Column(BIGINT, nullable=True, index=True)
    source_date = Column(Date, nullable=True)
    source_description = Column(Text, nullable=True)

    # New JSONB columns
    business_details = Column(JSONB, default={}, nullable=False)
    business_premise_address = Column(JSONB, default={}, nullable=False)
    applicant_residence_address = Column(JSONB, default={}, nullable=False)
    co_applicant_residence_address = Column(JSONB, default={}, nullable=False)
    customer_references = Column(JSONB, default={}, nullable=False)

    # Customer Salary Details — displayed only when profile_type = "Salaried"
    customer_salary_details = Column(JSONB, default={}, nullable=True)

    # ========== HYBRID PROPERTIES ==========
    @hybrid_property
    def current_business_type(self):
        """Returns business type from JSONB if exists, else from old column"""
        if self.business_details and isinstance(self.business_details, dict):
            return (
                self.business_details.get("type_of_business") or self.type_of_business
            )
        return self.type_of_business

    @hybrid_property
    def current_industry(self):
        if self.business_details and isinstance(self.business_details, dict):
            return self.business_details.get("industry") or self.industry
        return self.industry

    @hybrid_property
    def current_city(self):
        if self.business_premise_address and isinstance(
            self.business_premise_address, dict
        ):
            return self.business_premise_address.get("city") or self.city
        return self.city


class AccountStatusHistory(Base):
    __tablename__ = "account_status_history"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    account_id = Column(
        BIGINT, ForeignKey("accounts_merged.id"), nullable=False, index=True
    )
    company_id = Column(Integer, default=1, nullable=True, index=True)
    status = Column(String, nullable=False, index=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    total_time_stayed = Column(String, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    moved_by_id = Column(BIGINT, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # relationships
    account = relationship("Account", backref="status_histories")
    moved_by_user = relationship("User")
