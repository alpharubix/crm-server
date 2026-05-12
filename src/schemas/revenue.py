from typing import Optional

from pydantic import BaseModel


class Revenue(BaseModel):
    deal_id: int
    account_name: str
    lender_name: str
    reference_number: str
    income_booking_date: str
    type_of_revenue: str
    amount: float
    gst_amount: float

class RevenueUpdateSchema(BaseModel):

    lender_name: Optional[str] = None
    income_booking_date: Optional[str] = None
    type_of_revenue: Optional[str] = None
    amount: Optional[float] = None
    gst_amount: Optional[float] = None
    reference_number: Optional[str] = None

