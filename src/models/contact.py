from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.dialects.mysql import BIGINT
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
    id = Column(BIGINT, primary_key=True, index=True,autoincrement=False)

    # Relationship to Account (The Fix)
    # account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True, index=True)
    # Foreign Key (Links to Account Table)
    account_id = Column(BIGINT, ForeignKey("accounts.id"),index=True)
    owner_id = Column(BIGINT, ForeignKey("users.id"), index=True)
    # Relationship (Links to Account Object)
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
    created_by_id = Column(BIGINT,ForeignKey('users.id'), nullable=True)
    modified_by_id = Column(BIGINT,ForeignKey('users.id') ,nullable=True)
    created_time = Column(DateTime(timezone=True), server_default=func.now())
    modified_time = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    #making relationship with the other model
    contact_owner = relationship("User", foreign_keys = [owner_id],backref="contact_owner")
    parent_account = relationship("Account", foreign_keys=[account_id], backref="account_linked_contact")
    created_by = relationship('User',foreign_keys=[created_by_id],backref="contact_created_by")
    modified_by = relationship('User',foreign_keys=[modified_by_id],backref="contact_modified_by")