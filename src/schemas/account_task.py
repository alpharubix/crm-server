from datetime import datetime

from pydantic import BaseModel


class AccountTaskCreate(BaseModel):
    module_name: str = "Account"
    account_id: str | int
    task_type: str  # Call, Update Record, Email, Move Status
    task_description: str | None = None
    task_assigned_date_time: datetime | None = None
    task_due_date_time: datetime | None = None
    task_status: str = "Unassigned"  # Unassigned, Assigned, Pending, In Progress, Completed, Verified, Overdue
    assigned_to_id: str | int | None = None


class BulkAccountTaskCreate(BaseModel):
    account_ids: list[str | int]
    task_status: str | None = "Unassigned"
    task_assigned_date_time: datetime | None = None
    task_due_date_time: datetime | None = None
    task_description: str | None = None


class BulkTaskStatusUpdate(BaseModel):
    task_ids: list[str | int]
    task_status: str


class AccountTaskUpdate(BaseModel):
    task_type: str | None = None
    task_description: str | None = None
    task_assigned_date_time: datetime | None = None
    task_due_date_time: datetime | None = None
    task_status: str | None = None
    assigned_to_id: str | int | None = None
    account_id: str | int | None = None


class AccountTaskSchema(BaseModel):
    id: str | int
    module_name: str
    account_id: str | int
    account_name: str | None = None
    account_owner: str | None = None
    account_owner_id: str | int | None = None
    account_status: str | None = None
    account_stage: str | None = None
    call_back_date_status: str | None = None
    task_type: str
    task_description: str | None = None
    task_assigned_date_time: datetime | None = None
    task_due_date_time: datetime | None = None
    task_status: str
    assigned_to_id: str | int | None = None
    assigned_to_name: str | None = None
    created_by_id: str | int | None = None
    modified_by_id: str | int | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AccountTaskListResponse(BaseModel):
    data: list[AccountTaskSchema]
    page_info: dict
