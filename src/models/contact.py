from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    
    # Links to accounts table
    account_id = Column(Integer, ForeignKey("accounts.id"))

    first_name = Column(String)
    last_name = Column(String)
    email = Column(String)
    phone = Column(String)

    # STRING REFERENCE
    account = relationship("Account", back_populates="contacts")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())