import enum

from sqlalchemy import (
    JSON,
    BigInteger,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class PriorityEnum(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ProjectTypeEnum(str, enum.Enum):
    new = "new"
    upgradation = "upgradation"
    modification = "modification"
    bug = "bug"


class ProjectComment(Base):
    __tablename__ = "project_comments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    project_id = Column(
        BigInteger, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project = relationship("Project", back_populates="comments")
    user = relationship("User", foreign_keys=[user_id])


class StatusEnum(str, enum.Enum):
    planning = "planning"
    active = "active"
    on_hold = "on_hold"
    completed = "completed"
    cancelled = "cancelled"
    pending_for_approve = "pending_for_approve"
    pending_for_review = "pending_for_review"
    rejected = "rejected"


class TaskStatusEnum(str, enum.Enum):
    todo = "todo"
    in_progress = "in_progress"
    review = "review"
    done = "done"


class TaskTypeEnum(str, enum.Enum):
    feature = "feature"
    bug = "bug"
    enhancement = "enhancement"
    research = "research"


class Project(Base):
    __tablename__ = "projects"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(Enum(PriorityEnum), nullable=True)
    status = Column(
        Enum(StatusEnum), nullable=False, default=StatusEnum.pending_for_approve
    )
    created_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    approver_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    modified_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    modified_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    actioner_ids = Column(ARRAY(BigInteger), nullable=True, default=[])
    modifier = relationship("User", foreign_keys=[modified_by])
    creator = relationship("User", foreign_keys=[created_by])
    tasks = relationship("Task", back_populates="project")
    project_type = Column(Enum(ProjectTypeEnum), nullable=True)
    attachment_links = Column(JSON, default=list)
    comments = relationship(
        "ProjectComment", back_populates="project", cascade="all, delete-orphan"
    )


class Task(Base):
    __tablename__ = "tasks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    type = Column(Enum(TaskTypeEnum), nullable=False, default=TaskTypeEnum.feature)
    priority = Column(Enum(PriorityEnum), nullable=True)
    status = Column(Enum(TaskStatusEnum), nullable=False, default=TaskStatusEnum.todo)
    project_id = Column(BigInteger, ForeignKey("projects.id"), nullable=False)
    assignee_id = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_by = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    modified_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    modified_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    start_date = Column(DateTime(timezone=True), nullable=True)
    end_date = Column(DateTime(timezone=True), nullable=True)
    actual_completion_date = Column(DateTime(timezone=True), nullable=True)
    attachment_links = Column(JSON, default=list)

    project = relationship("Project", back_populates="tasks")
    assignee = relationship("User", foreign_keys=[assignee_id])
    creator = relationship("User", foreign_keys=[created_by])
    modifier = relationship("User", foreign_keys=[modified_by])
    comments = relationship(
        "TaskComment", back_populates="task", cascade="all, delete-orphan"
    )


class TaskComment(Base):
    __tablename__ = "task_comments"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(
        BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task = relationship("Task", back_populates="comments")
    user = relationship("User", foreign_keys=[user_id])


# Add this to your existing Task model
# comments = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan")
