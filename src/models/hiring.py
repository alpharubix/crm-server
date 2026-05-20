from sqlalchemy import BIGINT, Column, DateTime, ForeignKey, Integer, String, Text, Float
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class JobRequirement(Base):
    __tablename__ = "job_requirements"

    id = Column(BIGINT, primary_key=True, autoincrement=True)

    # --- Section: Hiring Requirements ---
    hiring_position = Column(String, nullable=True, index=True)
    department = Column(String, nullable=True, index=True)
    level = Column(String, nullable=True)
    sub_level = Column(String, nullable=True)
    no_of_vacancies = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    age_limit = Column(Integer, nullable=True)  # "Age Limit"
    hiring_location_city = Column(String, nullable=True, index=True)
    
    # --- Section: Compensation & Timeline ---
    min_annual_ctc = Column(String, nullable=True)
    max_annual_ctc = Column(String, nullable=True)
    position_open_date = Column(DateTime(timezone=True), nullable=True)
    tentative_joining_date = Column(DateTime(timezone=True), nullable=True)  # "Joining Date"
    tat = Column(Integer, nullable=True)  # Duration (days)
    qualification = Column(String, nullable=True)  # Single Line baseline field

    # --- Section: Education (Multi-select) ---
    educational_qualification_ug = Column(ARRAY(String), nullable=True)
    educational_qualification_pg = Column(ARRAY(String), nullable=True)

    # --- Section: Work Experience ---
    experience = Column(String, nullable=True)  # Picklist (0-2y, 2-4y, etc.)
    work_experience_department = Column(String, nullable=True)
    work_description = Column(Text, nullable=True)
    
    # --- Section: Skills & Languages ---
    skills = Column(String, nullable=True)  # "Skills Required"
    language_proficiency = Column(ARRAY(String), nullable=True)

    # --- Section: Roles & Core Assignment ---
    reporting_manager = Column(String, nullable=True)
    job_description = Column(Text, nullable=True)
    approver_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)
    assignee_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)

    # Audit
    created_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    modified_time = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    approver = relationship("User", foreign_keys=[approver_id])
    assignee = relationship("User", foreign_keys=[assignee_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    candidates = relationship("Candidate", back_populates="job_requirement")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(BIGINT, primary_key=True, autoincrement=True)
    job_requirement_id = Column(BIGINT, ForeignKey("job_requirements.id"), nullable=True, index=True)

    # --- Section: Candidate Info ---
    candidate_name = Column(String, nullable=False)
    candidate_status = Column(String, nullable=True, index=True)
    location_city = Column(String, nullable=True)
    status_date = Column(DateTime(timezone=True), nullable=True)
    call_back_date = Column(DateTime(timezone=True), nullable=True)
    phone_no = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True)
    resume = Column(String, nullable=True)

    # --- Section: Education ---
    educational_qualification_ug = Column(String, nullable=True)
    year_of_passing_ug = Column(String, nullable=True)
    educational_qualification_pg = Column(String, nullable=True)
    year_of_passing_pg = Column(String, nullable=True)

    # --- Section: Work Experience ---
    work_experience = Column(String, nullable=True)  # Duration (2y 8m)
    industry = Column(String, nullable=True)

    # --- Section: Skills & Languages ---
    skills = Column(String, nullable=True)
    language_proficiency = Column(ARRAY(String), nullable=True)

    # --- Section: Candidate Rating Block ---
    rating = Column(Float, nullable=True)
    feedback_status = Column(String, nullable=True)
    feedback_form_link = Column(String, nullable=True)
    rating_submitted_by = Column(BIGINT, ForeignKey("users.id"), nullable=True)

    # --- Section: Ownership ---
    assignee_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)

    # Audit
    created_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    modified_time = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    job_requirement = relationship("JobRequirement", back_populates="candidates")
    assignee = relationship("User", foreign_keys=[assignee_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    submitted_by_user = relationship("User", foreign_keys=[rating_submitted_by])