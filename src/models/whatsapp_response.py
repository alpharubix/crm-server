from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class WhatsAppTemplateResponse(Base):
    __tablename__ = "whatsapp_template_responses"

    id = Column(BIGINT, primary_key=True, index=True, autoincrement=True)
    company_id = Column(Integer, default=1, nullable=True, index=True)

    # Relationships to Account & Contact in PostgreSQL
    account_id = Column(BIGINT, ForeignKey("accounts_merged.id"), nullable=True, index=True)
    contact_id = Column(BIGINT, ForeignKey("contacts_merged.id"), nullable=True, index=True)

    # Customer identifier
    customer_phone = Column(String, nullable=False, index=True)

    # Template Information
    template_name = Column(String, nullable=False, index=True)
    template_language = Column(String, nullable=True)

    # Customer Response
    response_status = Column(String, nullable=False, index=True)  # "interested", "not_interested", "other"
    button_text = Column(String, nullable=True)                  # e.g., "Interested", "Yes", "No"
    button_payload = Column(String, nullable=True)               # e.g., "INTERESTED", "RESP_YES"

    # Meta message tracking
    outbound_wamid = Column(String, nullable=True, index=True)   # WAMID of the sent template
    inbound_wamid = Column(String, nullable=True, index=True)    # WAMID of customer's button reply

    # Extra context / custom payload data
    extra_data = Column(JSONB, default={}, nullable=False)

    # Timestamps
    responded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    account = relationship("Account", backref="whatsapp_responses")
    contact = relationship("Contact", backref="whatsapp_responses")
