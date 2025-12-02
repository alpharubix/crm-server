from sqlalchemy import Column, Integer, Numeric, String, DateTime
from ..database import Base
from datetime import datetime, timezone


class Lead(Base):
    __tablename__ = "leads"

    address = Column(String)
    annual_revenue = Column(Numeric(15, 2))
    assignment_date = Column(DateTime)
    average_time_spent_minutes = Column(Integer)
    business_status = Column(String)
    call_back_datetime = Column(DateTime)
    city = Column(String)
    company = Column(String)
    country = Column(String)
    created_by = Column(String)
    days_visited = Column(Integer)
    description = Column(String)
    distributor_code = Column(String, index=True)
    first_name = Column(String)
    first_page_visited = Column(String)
    first_visit = Column(DateTime)
    full_name = Column(String)
    industry = Column(String)
    last_name = Column(String)
    email = Column(String, unique=True, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

