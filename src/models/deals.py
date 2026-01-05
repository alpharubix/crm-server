from sqlalchemy import (
    Column,
    String,
    Date,
    DateTime,
    Numeric,
    ForeignKey,
    BIGINT,
    Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database import Base


class Deal(Base):
    __tablename__ = "deals"

    # ─────────────────────────────
    # Primary Key
    # ─────────────────────────────
    id = Column(BIGINT, primary_key=True, index=True, autoincrement=False)

    # ─────────────────────────────
    # Core Identifiers
    # ─────────────────────────────
    account_name = Column(String, nullable=False, index=True)
    deal_name = Column(String, nullable=False, index=True)

    # ─────────────────────────────
    # Ownership & Audit
    # ─────────────────────────────
    owner_id = Column(BIGINT, ForeignKey("users.id"), index=True)
    created_by_id = Column(BIGINT, ForeignKey("users.id"), nullable=False)
    modified_by_id = Column(BIGINT, ForeignKey("users.id"), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now()
    )

    # ─────────────────────────────
    # High-Query / Filter Fields
    # ─────────────────────────────
    deal_type = Column(String, index=True)
    deal_status = Column(String, index=True)
    stage = Column(String, index=True)
    deal_approval_status = Column(String, index=True)

    loan_type = Column(String, index=True)
    lender_name = Column(String, index=True)

    closing_date = Column(Date, index=True)
    disbursement_date = Column(Date, index=True)

    sanction_amount = Column(Numeric(15, 2), index=True)
    disbursed_amount = Column(Numeric(15, 2))

    # ─────────────────────────────
    # Flexible / Custom Fields
    # ─────────────────────────────
    custom_fields = Column(JSONB, default={}, nullable=False)

    # ─────────────────────────────
    # Relationships
    # ─────────────────────────────
    deal_owner = relationship(
        "User",
        foreign_keys=[owner_id],
        backref="owned_deals"
    )

    created_by = relationship(
        "User",
        foreign_keys=[created_by_id],
        backref="deals_created"
    )

    modified_by = relationship(
        "User",
        foreign_keys=[modified_by_id],
        backref="deals_modified"
    )

    # ─────────────────────────────
    # Indexes (Explicit like CRM-scale systems)
    # ─────────────────────────────
    __table_args__ = (
        Index("ix_deals_account_name", "account_name"),
        Index("ix_deals_deal_name", "deal_name"),
        Index("ix_deals_deal_type", "deal_type"),
        Index("ix_deals_deal_status", "deal_status"),
        Index("ix_deals_stage", "stage"),
        Index("ix_deals_deal_approval_status", "deal_approval_status"),
        Index("ix_deals_loan_type", "loan_type"),
        Index("ix_deals_lender_name", "lender_name"),
        Index("ix_deals_closing_date", "closing_date"),
        Index("ix_deals_disbursement_date", "disbursement_date"),
        Index("ix_deals_sanction_amount", "sanction_amount"),
    )
