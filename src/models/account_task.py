from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import (
    BIGINT,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base

IST = ZoneInfo("Asia/Kolkata")


def get_call_back_info(call_back_dt):
    if not call_back_dt:
        return "Blank", "Refers to the field not filled up"

    now_utc = datetime.now(UTC)
    try:
        now_ist = now_utc.astimezone(IST)
        cb_ist = (
            call_back_dt.astimezone(IST)
            if getattr(call_back_dt, "tzinfo", None)
            else call_back_dt.replace(tzinfo=IST)
        )
    except Exception:
        now_ist = now_utc
        cb_ist = call_back_dt

    today_date = now_ist.date()
    cb_date = cb_ist.date()

    if cb_ist < now_ist and cb_date < today_date:
        return "Overdue", "Refers to the field past the date"
    elif cb_date == today_date:
        return (
            "Due Today",
            'Refers to the calendar date Today starting from "00:00" to "23:59"',
        )
    elif cb_date == today_date + timedelta(days=1):
        return (
            "Due Tomorrow",
            'Refers to the calendar date Tomorrow starting from "00:00" to "23:59"',
        )

    start_of_this_week = today_date - timedelta(days=today_date.weekday())
    end_of_this_week = start_of_this_week + timedelta(days=6)
    start_of_next_week = end_of_this_week + timedelta(days=1)
    end_of_next_week = start_of_next_week + timedelta(days=6)

    if start_of_this_week <= cb_date <= end_of_this_week:
        return (
            "Due This Week",
            "Refers to the current calendar week starting Monday to Sunday",
        )
    elif start_of_next_week <= cb_date <= end_of_next_week:
        return (
            "Due Next Week",
            "Refers to the next calendar week starting Monday to Sunday",
        )
    elif cb_date > end_of_next_week:
        return "Due Dates", "As per the dates selected in the date select field"
    else:
        return "Overdue", "Refers to the field past the date"


class AccountTask(Base):
    __tablename__ = "account_tasks"

    id = Column(BIGINT, primary_key=True, autoincrement=True, index=True)
    company_id = Column(Integer, default=1, nullable=True, index=True)
    module_name = Column(String, default="Account", nullable=False)

    # Linked Account
    account_id = Column(
        BIGINT, ForeignKey("accounts_merged.id"), nullable=False, index=True
    )

    # Task Fields
    task_type = Column(
        String(100), nullable=False
    )  # Call, Update Record, Email, Move Status
    task_description = Column(Text, nullable=True)
    task_assigned_date_time = Column(DateTime(timezone=True), nullable=True)
    task_due_date_time = Column(DateTime(timezone=True), nullable=True)
    task_status = Column(String(50), default="Unassigned", nullable=False, index=True)
    # Options: Unassigned, Assigned, Pending, In Progress, Completed, Verified, Overdue

    # Target & Completion Fields
    target_account_status = Column(String(100), nullable=True)
    target_call_back_date_time = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Assignee & Audit
    assigned_to_id = Column(BIGINT, ForeignKey("users.id"), nullable=True, index=True)
    created_by_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)
    modified_by_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    account = relationship("Account", backref="account_tasks")
    assigned_to = relationship(
        "User", foreign_keys=[assigned_to_id], backref="assigned_account_tasks"
    )
    created_by = relationship(
        "User", foreign_keys=[created_by_id], backref="created_account_tasks"
    )
    modified_by = relationship(
        "User", foreign_keys=[modified_by_id], backref="modified_account_tasks"
    )

    @hybrid_property
    def account_name(self):
        return self.account.account_name if self.account else None

    @hybrid_property
    def account_status(self):
        return self.account.account_status if self.account else None

    @hybrid_property
    def account_stage(self):
        return self.account.account_stage if self.account else None

    @hybrid_property
    def account_owner(self):
        if self.account and self.account.owner:
            return self.account.owner.full_name or self.account.owner.email
        return None

    @hybrid_property
    def account_owner_id(self):
        return self.account.account_owner_id if self.account else None

    @hybrid_property
    def call_back_date_status(self):
        if not self.account or not self.account.call_back_date_time:
            return "Blank"
        status_name, _ = get_call_back_info(self.account.call_back_date_time)
        return status_name

    @hybrid_property
    def computed_task_status(self):
        if self.task_status in ["Completed", "Verified"]:
            return self.task_status
        now = datetime.now(UTC)
        if self.task_due_date_time:
            due = self.task_due_date_time
            if due.tzinfo is None:
                due = due.replace(tzinfo=UTC)
            if due < now:
                return "Overdue"
            if self.task_assigned_date_time:
                assigned = self.task_assigned_date_time
                if assigned.tzinfo is None:
                    assigned = assigned.replace(tzinfo=UTC)
                if due < assigned:
                    return "Overdue"
        return self.task_status
