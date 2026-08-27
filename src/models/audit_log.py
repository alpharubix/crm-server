from sqlalchemy import BigInteger, Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ..database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    company_id = Column(Integer, default=1, nullable=True, index=True)
    user_id = Column(BigInteger, nullable=False)
    user_role = Column(String(50), nullable=False)
    action = Column(String(20), nullable=False)  # CREATED / UPDATED
    entity = Column(String(100), nullable=False)  # e.g. "Contact"
    entity_id = Column(BigInteger, nullable=False)
    payload = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
