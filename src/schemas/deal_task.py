from datetime import datetime

from pydantic import BaseModel


class DealTaskCreate(BaseModel):
    module_name: str = "Deal"
    deal_id: str | int
    task_type: str  # Call, Update Record, Email, Move Status
    task_description: str | None = None
    task_assigned_date_time: datetime | None = None
    task_due_date_time: datetime | None = None
    task_status: str = "Unassigned"  # Unassigned, Assigned, Pending, In Progress, Completed, Verified, Overdue
    assigned_to_id: str | int | None = None
    target_deal_status: str | None = None


class BulkDealTaskCreate(BaseModel):
    deal_ids: list[str | int]
    task_status: str | None = "Unassigned"
    task_assigned_date_time: datetime | None = None
    task_due_date_time: datetime | None = None
    task_description: str | None = None


class BulkDealTaskStatusUpdate(BaseModel):
    task_ids: list[str | int]
    task_status: str


class DealTaskUpdate(BaseModel):
    task_type: str | None = None
    task_description: str | None = None
    task_assigned_date_time: datetime | None = None
    task_due_date_time: datetime | None = None
    task_status: str | None = None
    assigned_to_id: str | int | None = None
    deal_id: str | int | None = None
    target_deal_status: str | None = None
    completed_at: datetime | None = None


class DealTaskSchema(BaseModel):
    id: str
    module_name: str
    deal_id: str
    deal_name: str | None = None
    account_id: str | None = None
    account_name: str | None = None
    account_owner: str | None = None
    account_owner_id: str | None = None
    deal_owner: str | None = None
    deal_owner_id: str | None = None
    deal_status: str | None = None
    deal_stage: str | None = None
    loan_type: str | None = None
    lender_name: str | None = None
    call_back_date_status: str | None = None
    call_back_date_time: str | None = None
    deal_assigned_date_time: str | None = None
    task_type: str
    task_description: str | None = None
    task_assigned_date_time: datetime | None = None
    task_due_date_time: datetime | None = None
    task_status: str
    target_deal_status: str | None = None
    completed_at: datetime | None = None
    assigned_to_id: str | None = None
    assigned_to_name: str | None = None
    created_by_id: str | None = None
    created_by_name: str | None = None
    modified_by_id: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DealTaskListResponse(BaseModel):
    data: list[DealTaskSchema]
    page_info: dict
