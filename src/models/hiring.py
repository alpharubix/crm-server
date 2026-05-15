from sqlalchemy import BIGINT, Column, DateTime, ForeignKey, Integer, String, Text, Float
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
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
    age_limit = Column(Integer, nullable=True) # Max Age Limit in Excel
    hiring_location_city = Column(String, nullable=True, index=True)
    
    # --- Section: Compensation & Timeline ---
    min_annual_ctc = Column(String, nullable=True)
    max_annual_ctc = Column(String, nullable=True)
    position_open_date = Column(DateTime(timezone=True), nullable=True)
    tentative_joining_date = Column(DateTime(timezone=True), nullable=True) # "Joining Date" in Excel
    tat = Column(Integer, nullable=True) # Duration (days)
    
    # --- Section: Education (Multi-select in Excel) ---
    educational_qualification_ug = Column(ARRAY(String), nullable=True)
    educational_qualification_pg = Column(ARRAY(String), nullable=True)
    qualification = Column(String, nullable=True) # "Qualification - Single Line" from Detail view

    # --- Section: Work Experience (Distinct section in Excel) ---
    experience = Column(String, nullable=True) # Overall Experience Picklist
    work_experience_department = Column(String, nullable=True) # "Department" under Work Exp section
    work_description = Column(Text, nullable=True) # "Work Description" multi-line
    
    # --- Section: Skills & Languages ---
    skills = Column(String, nullable=True) # "Skills Required"
    language_proficiency = Column(ARRAY(String), nullable=True)

    # --- Section: Roles & Job Description ---
    reporting_manager = Column(String, nullable=True)
    job_description = Column(Text, nullable=True)
    
    # --- Section: Assignment ---
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
    candidate_status = Column(String, nullable=True, index=True) # Picklist in Excel
    location_city = Column(String, nullable=True)
    status_date = Column(DateTime(timezone=True), nullable=True) # Date (dd-mm-yyyy)
    call_back_date = Column(DateTime(timezone=True), nullable=True) # Date (dd-mm-yyyy)
    phone_no = Column(String, nullable=True)
    email = Column(String, nullable=True, index=True)
    resume = Column(String, nullable=True) # Attachment / Link

    # --- Section: Education ---
    educational_qualification_ug = Column(String, nullable=True) # Picklist
    year_of_passing_ug = Column(String, nullable=True) # YYYY
    educational_qualification_pg = Column(String, nullable=True) # Picklist
    year_of_passing_pg = Column(String, nullable=True) # YYYY

    # --- Section: Work Experience ---
    work_experience = Column(String, nullable=True) # Duration (e.g. 2y 8m)
    industry = Column(String, nullable=True) # Picklist

    # --- Section: Skills & Languages ---
    skills = Column(String, nullable=True)
    language_proficiency = Column(ARRAY(String), nullable=True) # Multi-Select

    # --- Section: Candidate Rating (Matches Excel + Footer) ---
    rating = Column(Float, nullable=True) # 1-5 rating
    feedback_status = Column(String, nullable=True) # "Submitted", "Pending"
    feedback_form_link = Column(String, nullable=True) # Link to "Feedback Form" sheet data
    rating_submitted_by = Column(BIGINT, ForeignKey("users.id"), nullable=True)

    # --- Ownership ---
    assignee_id = Column(BIGINT, ForeignKey("users.id"), nullable=True) # User
    created_by_id = Column(BIGINT, ForeignKey("users.id"), nullable=True)

    # Audit
    created_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    modified_time = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    job_requirement = relationship("JobRequirement", back_populates="candidates")
    assignee = relationship("User", foreign_keys=[assignee_id])
    created_by = relationship("User", foreign_keys=[created_by_id])
    submitted_by_user = relationship("User", foreign_keys=[rating_submitted_by])