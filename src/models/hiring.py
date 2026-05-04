from sqlalchemy import BIGINT, Column, DateTime, ForeignKey, Integer, String, Text, Float
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..database import Base


class JobRequirement(Base):
    __tablename__ = "job_requirements"

    id = Column(BIGINT, primary_key=True, autoincrement=True)

    # Core fields
    hiring_position = Column(String, nullable=True, index=True)
    department = Column(String, nullable=True, index=True)
    level = Column(String, nullable=True)
    sub_level = Column(String, nullable=True)
    experience = Column(String, nullable=True)
    skills = Column(String, nullable=True)
    min_annual_ctc = Column(String, nullable=True)
    max_annual_ctc = Column(String, nullable=True)
    position_open_date = Column(DateTime(timezone=True), nullable=True)
    no_of_vacancies = Column(Integer, nullable=True)
    tentative_joining_date = Column(DateTime(timezone=True), nullable=True)
    tat = Column(Integer, nullable=True)  # Duration in days
    age_limit = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    reporting_manager = Column(String, nullable=True)
    qualification = Column(String, nullable=True)
    hiring_location_city = Column(String, nullable=True, index=True)
    language_proficiency = Column(ARRAY(String), nullable=True)
    job_description = Column(Text, nullable=True)

    # Education
    educational_qualification_ug = Column(ARRAY(String), nullable=True)
    educational_qualification_pg = Column(ARRAY(String), nullable=True)

    # Work experience section
    work_experience = Column(String, nullable=True)
    work_experience_department = Column(String, nullable=True)
    work_description = Column(Text, nullable=True)

    # Assignment / ownership
    approver_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)
    assignee_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)

    # Audit
    created_time = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    modified_time = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    approver = relationship("User", foreign_keys=[approver_id])
    assignee = relationship("User", foreign_keys=[assignee_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    # candidates = relationship("Candidate", back_populates="job_requirement")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(BIGINT, primary_key=True, autoincrement=True)

    # Parent FK
    job_requirement_id = Column(
        BIGINT, ForeignKey("job_requirements.id"), nullable=False, index=True
    )

    # Core fields
    candidate_name = Column(String, nullable=False)
    candidate_status = Column(String, nullable=True, index=True)
    status_date = Column(DateTime(timezone=True), nullable=True)
    call_back_date = Column(DateTime(timezone=True), nullable=True)
    phone_no = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True)
    location_city = Column(String, nullable=True)
    resume = Column(String, nullable=True)  # Drive link

    # Education
    educational_qualification_ug = Column(String, nullable=True)
    year_of_passing_ug = Column(String, nullable=True)
    educational_qualification_pg = Column(String, nullable=True)
    year_of_passing_pg = Column(String, nullable=True)

    # Work experience
    work_experience = Column(String, nullable=True)  # e.g. "2y 8m"
    industry = Column(String, nullable=True)

    # Skills
    skills = Column(String, nullable=True)
    language_proficiency = Column(ARRAY(String), nullable=True)

    # Assignment
    assignee_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)

    # Audit
    created_time = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    modified_time = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    assignee = relationship("User", foreign_keys=[assignee_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    # job_requirement = relationship("JobRequirement", back_populates="candidates")
# Test