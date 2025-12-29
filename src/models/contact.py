from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base
from sqlalchemy.dialects.postgresql import JSONB

# class Contact(Base):
#     __tablename__ = "contacts"

#     id = Column(Integer, primary_key=True, index=True)
    
#     # Links to accounts table
#     account_id = Column(Integer, ForeignKey("accounts.id"))

#     first_name = Column(String)
#     last_name = Column(String)
#     email = Column(String)
#     phone = Column(String)

#     # STRING REFERENCE
#     account = relationship("Account", back_populates="contacts")

#     created_at = Column(DateTime(timezone=True), server_default=func.now())
#     updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
# 
# 
# from sqlalchemy import Column, Integer, String, DateTime, ForeignKey

class Contact(Base):
    __tablename__ = "contacts"

    # Primary Key
    id = Column(Integer, primary_key=True, index=True)

    # Relationship to Account (The Fix)
    # account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True, index=True)
    # Foreign Key (Links to Account Table)
    account_id = Column(Integer, ForeignKey("accounts.id"), index=True)
    
    # Relationship (Links to Account Object)
    account = relationship("Account", back_populates="contacts") # Requires 'contacts' rel in Account model
    # Identity
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    designation = Column(String, nullable=True)
    
    # Communication
    email = Column(String, unique=True, nullable=False, index=True)
    secondary_email = Column(String, nullable=True)
    mobile = Column(String, nullable=True, unique=True)
    phone = Column(String, nullable=True)

    # Business Relations
    lead_source = Column(String, nullable=True, index=True)

    # Address Information
    street = Column(String, nullable=True)
    city = Column(String, nullable=True, index=True)
    state = Column(String, nullable=True, index=True)
    country = Column(String, nullable=True)
    pincode = Column(String, nullable=True)

    # Flexible Fields
    custom_fields = Column(JSONB, default={}, nullable=False)

    # System Audit
    created_by = Column(String, nullable=True)
    modified_by = Column(String, nullable=True)
    created_time = Column(DateTime(timezone=True), server_default=func.now())
    modified_time = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())