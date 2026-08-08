from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import BIGINT
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base

class DealDocument(Base):
    __tablename__ = "deal_documents_merged"

    id = Column(BIGINT, primary_key=True, autoincrement=True, index=True)
    company_id = Column(Integer, default=1, nullable=False, index=True)
    deal_id = Column(BIGINT, ForeignKey("deals_merged.id"), nullable=False, index=True)

    module = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    from_date = Column(DateTime(timezone=True), nullable=True)
    to_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(50), nullable=True)
    link = Column(Text, nullable=True)

    created_by = Column(BIGINT, nullable=True)
    modified_by = Column(BIGINT, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    deal = relationship("Deal", back_populates="documents")