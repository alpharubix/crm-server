from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from src.database import get_mongodb

router = APIRouter(tags=["Tele CRM"])


@router.post("/call-details")
def add_call_details(
    payload: dict[str, Any],
    mongo_db: Database = Depends(get_mongodb),
):
    try:
        doc = payload.copy()
        doc["created_at"] = datetime.now(timezone.utc)

        result = mongo_db["tele-crm-calls"].insert_one(doc)
        doc["_id"] = str(result.inserted_id)
        doc["created_at"] = doc["created_at"].isoformat()

        return {
            "status": "success",
            "message": "Call details saved successfully",
            "inserted_id": doc["_id"],
            "data": doc,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save call details: {str(e)}",
        )

