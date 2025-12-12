from sqlalchemy import Column, Integer, Numeric, String, DateTime
from sqlalchemy.sql import func
from ..database import Base

class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)

    # --- Schema Required Fields (Critical for your Form) ---
    # These match the 'LeadrCreate' schema requirements
    full_name = Column(String)       # Maps to schema 'name'
    phone_number = Column(String)    # Added (was missing in your list)
    email = Column(String, unique=True, nullable=False)
    pan = Column(String)             # Added (was missing in your list)
    gstin = Column(String)           # Added (was missing in your list)

    # --- Your Detailed Data Fields (from your list) ---
    address = Column(String, nullable=True)
    annual_revenue = Column(Numeric(15, 2), nullable=True)
    assignment_date = Column(DateTime, nullable=True)
    business_status = Column(String, default="New") # e.g. New, Contacted
    city = Column(String, nullable=True)
    company = Column(String, nullable=True)
    country = Column(String, nullable=True)
    created_by = Column(String, nullable=True)
    description = Column(String, nullable=True)
    distributor_code = Column(String, index=True, nullable=True)
    first_name = Column(String, nullable=True) # Optional if using full_name
    last_name = Column(String, nullable=True)  # Optional if using full_name
    industry = Column(String, nullable=True)

    # --- System Timestamps ---
    # using func.now() is often safer for Postgres than python datetime
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

