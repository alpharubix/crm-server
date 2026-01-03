# from sqlalchemy import Column, Integer, Numeric, String, DateTime
# from sqlalchemy.sql import func
# from ..database import Base

# class Account(Base):
#     __tablename__ = "accounts"

#     id = Column(Integer, primary_key=True, index=True)

#     # --- Schema Required Fields (Critical for your Form) ---
#     # These match the 'AccountCreate' schema requirements
#     full_name = Column(String)       # Maps to schema 'name'
#     phone_number = Column(String)    # Added (was missing in your list)
#     email = Column(String, unique=True, nullable=False)
#     pan = Column(String)             # Added (was missing in your list)
#     gstin = Column(String)           # Added (was missing in your list)

#     # --- Your Detailed Data Fields (from your list) ---
#     address = Column(String, nullable=True)
#     annual_revenue = Column(Numeric(15, 2), nullable=True)
#     assignment_date = Column(DateTime, nullable=True)
#     business_status = Column(String, default="New") # e.g. New, Contacted
#     city = Column(String, nullable=True)
#     company = Column(String, nullable=True)
#     country = Column(String, nullable=True)
#     created_by = Column(String, nullable=True)
#     description = Column(String, nullable=True)
#     distributor_code = Column(String, index=True, nullable=True)
#     first_name = Column(String, nullable=True) # Optional if using full_name
#     last_name = Column(String, nullable=True)  # Optional if using full_name
#     industry = Column(String, nullable=True)

#     # --- System Timestamps ---
#     # using func.now() is often safer for Postgres than python datetime
#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())


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
    phone = Column(String, unique=True, nullable=False)
    
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