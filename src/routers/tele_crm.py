from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.database import Database

from src.controllers.tele_crm import (
    sync_all_telecrm_leads,
    sync_yesterday_telecrm_leads,
)
from src.database import get_mongodb

router = APIRouter(tags=["Tele CRM"])


@router.post("/telecrm/sync-all")
def sync_all_telecrm(
    mongo_db: Database = Depends(get_mongodb),
):
    try:
        result = sync_all_telecrm_leads(mongo_db)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.post("/telecrm/sync-yesterday")
def sync_yesterday_telecrm(
    target_date: date | None = Query(
        default=None,
        description="Optional date (YYYY-MM-DD) to sync. Defaults to yesterday.",
    ),
    mongo_db: Database = Depends(get_mongodb),
):
    try:
        result = sync_yesterday_telecrm_leads(
            target_date=target_date,
            mongo_db=mongo_db,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
