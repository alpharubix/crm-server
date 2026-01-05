from sqlalchemy import Column, Integer, String, DateTime, Boolean, BIGINT, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
from ..database import Base

class Account(Base):
    __tablename__ = "accounts"

    # Primary Key
    id = Column(BIGINT, primary_key=True,autoincrement=False)
    # Identity & Contact (Core)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String, unique=False, nullable=False)
    account_name = Column(String, nullable=True,index=True)
    # Workflow & Assignment (Core - Filtered)
    account_owner_id = Column(BIGINT, ForeignKey('users.id'), nullable=False, index=True)
    account_status = Column(String, nullable=True, index=True)
    account_stage = Column(String, nullable=True, index=True)
    source = Column(String, nullable=True, index=True)
    business_status = Column(String, nullable=True, index=True)
    distributor_code = Column(String, nullable=True, index=True)
    
    # Business Details (Core - Filtered)
    type_of_business = Column(String, nullable=True, index=True)
    industry = Column(String, nullable=True, index=True)
    
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
        DateTime(timezone=True),  # <--- Enables timezone storage
        server_default=func.now(),  # <--- Uses the Database's clock (Safer)
        onupdate=func.now(),
        nullable=False
    )
    # Self-referencing Foreign Keys
    created_by_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)
    created_by = relationship(
        "User",
        foreign_keys=[created_by_id],
        backref="user_created_by_id"
    )

    owner = relationship(
        "User",
        foreign_keys=[account_owner_id],
        backref="account_owner"
    )