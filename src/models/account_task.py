from datetime import datetime, timezone, timedelta
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

class AccountTask(Base):
    __tablename__ = "account_tasks"

    id = Column(BIGINT, primary_key=True, autoincrement=True, index=True)
    company_id = Column(Integer, default=1, nullable=True, index=True)
    module_name = Column(String, default="Account", nullable=False)

    # Linked Account
    account_id = Column(BIGINT, ForeignKey("accounts_merged.id"), nullable=False, index=True)

    # Task Fields
    task_type = Column(String(100), nullable=False)  # Call, Update Record, Email, Move Status
    task_description = Column(Text, nullable=True)
    task_assigned_date_time = Column(DateTime(timezone=True), nullable=True)
    task_due_date_time = Column(DateTime(timezone=True), nullable=True)
    task_status = Column(String(50), default="Unassigned", nullable=False, index=True)
    # Options: Unassigned, Assigned, Pending, In Progress, Completed, Verified, Overdue

    # Assignee & Audit
    assigned_to_id = Column(BIGINT, ForeignKey("users.id"), nullable=True, index=True)
    created_by_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)
    modified_by_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    account = relationship("Account", backref="account_tasks")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id], backref="assigned_account_tasks")
    created_by = relationship("User", foreign_keys=[created_by_id], backref="created_account_tasks")
    modified_by = relationship("User", foreign_keys=[modified_by_id], backref="modified_account_tasks")

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
        
        cb_dt = self.account.call_back_date_time
        now = datetime.now(timezone.utc)
        
        try:
            now_ist = now.astimezone(IST).date()
            cb_ist = cb_dt.astimezone(IST).date() if cb_dt.tzinfo else cb_dt.date()
        except Exception:
            now_ist = now.date()
            cb_ist = cb_dt.date()

        if cb_ist < now_ist:
            return "Overdue"
        elif cb_ist == now_ist:
            return "Due Today"
        elif cb_ist == now_ist + timedelta(days=1):
            return "Due Tomorrow"
        
        start_of_week = now_ist - timedelta(days=now_ist.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        start_of_next_week = end_of_week + timedelta(days=1)
        end_of_next_week = start_of_next_week + timedelta(days=6)

        if start_of_week <= cb_ist <= end_of_week:
            return "Due This Week"
        elif start_of_next_week <= cb_ist <= end_of_next_week:
            return "Due Next Week"
        else:
            return "Due Next Week"

    @hybrid_property
    def computed_task_status(self):
        if self.task_status in ["Completed", "Verified"]:
            return self.task_status
        if self.task_due_date_time:
            now = datetime.now(timezone.utc)
            due = self.task_due_date_time
            if due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            if due < now:
                return "Overdue"
        return self.task_status
