from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    BIGINT,
    func
)
from sqlalchemy.orm import relationship
from src.database import Base


class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    ticket_id = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(BIGINT, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    service = Column(String(100), nullable=False)
    priority = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="OPEN")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", foreign_keys=[user_id])
