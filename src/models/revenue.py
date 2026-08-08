from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    FLOAT,
    ForeignKey, BIGINT, DateTime,
)
from src.database import Base




from sqlalchemy.orm import relationship


class Revenue(Base):
    __tablename__ = "revenue_merged"

    id = Column(Integer, primary_key=True, autoincrement=True)

    company_id = Column(Integer, default=1, nullable=False, index=True)

    deal_id = Column(
        BIGINT,
        ForeignKey("deals_merged.id"),
        nullable=False
    )

    account_name = Column(String(255), nullable=False)

    lender_name = Column(String(255), nullable=False)

    reference_number = Column(String(255), nullable=False)

    income_booking_date = Column(Date, nullable=False)

    type_of_revenue = Column(String(100), nullable=False)

    gst_amount = Column(FLOAT, nullable=False)

    amount = Column(FLOAT, nullable=False)

    created_at = Column(DateTime, nullable=False)

    updated_at = Column(DateTime, nullable=True)

    owner_id = Column(
        BIGINT,
        ForeignKey("users.id"),
        nullable=False
    )

    created_by = Column(
        BIGINT,
        ForeignKey("users.id"),
        nullable=False
    )

    updated_by = Column(
        BIGINT,
        ForeignKey("users.id"),
        nullable=True
    )

    # ---------------- RELATIONSHIPS ---------------- #

    deal = relationship(
        "Deal",
        foreign_keys=[deal_id],
        back_populates="revenue"
    )

    revenue_owner = relationship(
        "User",
        foreign_keys=[owner_id]
    )

    creator = relationship(
        "User",
        foreign_keys=[created_by]
    )

    updater = relationship(
        "User",
        foreign_keys=[updated_by]
    )



