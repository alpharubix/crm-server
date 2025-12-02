from sqlalchemy import Column, Integer, Numeric, String, DateTime, Text
from sqlalchemy.sql import func
from ..database import Base
from datetime import datetime, timezone

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(255))
    full_name = Column(String(255))
    email = Column(String(255), index=True)
    designation = Column(String(255))
    account_name = Column(String(255)) 
    contact_owner = Column(String(255))
    address = Column(Text)
    description = Column(Text)
    average_time_spent_minutes = Column(Numeric(10, 2))
    days_visited = Column(Integer)
    first_page_visited = Column(String(2048))
    created_time = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(String(255))
    first_visit = Column(DateTime(timezone=True))
    last_activity_time = Column(DateTime(timezone=True), onupdate=func.now())