from annotated_types import Timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    BIGINT, func
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
from ..database import Base


class User(Base):
    __tablename__ = "users"

    # Primary Key (MANUAL — not auto-generated)
    id = Column(BIGINT, primary_key=True, autoincrement=False)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)

    zuid = Column(String(100), unique=True, nullable=True)
    role = Column(String(50), nullable=False)
    password = Column(String(255), nullable=False)

    created_time = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    modified_time = Column(
        DateTime(timezone=True),  # <--- Enables timezone storage
        server_default=func.now(),  # <--- Uses the Database's clock (Safer)
        onupdate=func.now(),
        nullable=False
    )
    # Self-referencing Foreign Keys
    created_by_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)
    modified_by_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)

    # Relationships (self-referential)
    created_by = relationship(
        "User",
        remote_side=[id],
        foreign_keys=[created_by_id],
        backref="created_users"
    )

    modified_by = relationship(
        "User",
        remote_side=[id],
        foreign_keys=[modified_by_id],
        backref="modified_users"
    )