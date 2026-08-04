from beanie import Document
from pydantic import Field
from datetime import datetime, date
from typing import List


class DistributorMaster(Document):
    # Basic Details
    anchor: str
    date_received: datetime = None
    enrollment_date: date = None

    distributor_code: int
    distributor_name: str

    # Location Details
    cfa_name: str = None
    region: str = None
    division: str = None

    city: str = None
    state: str = None
    pincode: str = None

    # Distributor Details
    distribution_type: str = None
    leap_non_leap: str = None

    # Contact Details
    email: str = None
    mobile_number: str = None
    phone_number: str = None

    # Tax Details
    gst_number: str = None
    pan_number: str = None

    # Sales Details
    sales_month_1: float = None
    sales_month_2: float = None
    sales_month_3: float = None
    sales_month_4: float = None
    sales_month_5: float = None
    sales_month_6: float = None
    sales_month_7: float = None
    sales_month_8: float = None
    sales_month_9: float = None
    sales_month_10: float = None
    sales_month_11: float = None
    sales_month_12: float = None

    # Audit Fields
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "distributor_master"
