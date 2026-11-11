import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.database import Database

from src.database import get_leads_gst_cibil_database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gst-cibil-reports", tags=["GST & CIBIL Reports"])


import re
from typing import Optional
from fastapi import Depends, HTTPException, Query


@router.get("")
async def get_gst_cibil_reports(
    db: Database = Depends(get_leads_gst_cibil_database),
    search: Optional[str] = Query(None, description="Search by GSTIN or Trade Name"),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
):
    """
    Get all reports with report_status mapped from gst_reference_tracker via reference_id
    """
    try:
        match_stage = {}
        if search and search.strip():
            escaped_term = re.escape(search.strip())
            match_stage = {
                "$or": [
                    {"gstin": {"$regex": escaped_term, "$options": "i"}},
                    {"report.entity.trade_name": {"$regex": escaped_term, "$options": "i"}},
                    {"report.entity.legal_name": {"$regex": escaped_term, "$options": "i"}},
                    {"reference_id": {"$regex": escaped_term, "$options": "i"}},
                ]
            }

        pipeline = []

        if match_stage:
            pipeline.append({"$match": match_stage})

        # Apply sort, skip, limit BEFORE lookup to optimize query execution
        pipeline.extend([
            {"$sort": {"_id": -1}},
            {"$skip": skip},
            {"$limit": limit},
            {
                "$lookup": {
                    "from": "gst_reference_tracker",
                    "localField": "reference_id",
                    "foreignField": "reference_id",
                    "as": "tracker",
                }
            },
            {
                "$addFields": {
                    "tracker_data": {"$arrayElemAt": ["$tracker", 0]}
                }
            },
            {
                "$project": {
                    "_id": 1,
                    "gstin": 1,
                    "reference_id": 1,
                    "report.entity.trade_name": 1,
                    "report.entity.legal_name": 1,
                    "report.entity.mobile": 1,
                    "report.entity.status": 1,
                    "report.bureau.rating": 1,
                    "report.report.generated_at": 1,
                    # Pull report_status from the matched tracker document
                    "tracker_report_status": "$tracker_data.report_status",
                    "tracker_request_stage": "$tracker_data.request_stage",
                }
            },
        ])

        # If using Motor (Async):
        # cursor = db["reports"].aggregate(pipeline)
        # docs = await cursor.to_list(length=limit)
        # total_count = await db["reports"].count_documents(match_stage)

        # If using PyMongo (Sync):
        docs = list(db["reports"].aggregate(pipeline))
        total_count = db["reports"].count_documents(match_stage)

        results = []
        for doc in docs:
            report_data = doc.get("report") or {}
            entity = report_data.get("entity") or {}
            bureau = report_data.get("bureau") or {}
            meta = report_data.get("report") or {}

            results.append(
                {
                    "id": str(doc["_id"]),
                    "gstin": doc.get("gstin") or entity.get("gstin") or "",
                    "name": entity.get("trade_name") or entity.get("legal_name") or "N/A",
                    "contact_number": entity.get("mobile") or "N/A",
                    "reference_id": doc.get("reference_id") or "",
                    "entity_status": entity.get("status") or "Active",
                    "report_status": doc.get("tracker_report_status") or "PENDING",
                    "request_stage": doc.get("tracker_request_stage") or "PENDING",
                    "bureau_rating": bureau.get("rating") or "Not Available",
                    "last_updated": meta.get("generated_at") or "N/A",
                }
            )

        return {
            "code": "SUCCESS",
            "message": "Reports fetched successfully",
            "data": results,
            "total": total_count,
        }
    except Exception as e:
        logger.exception("Error fetching GST CIBIL reports: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch reports: {str(e)}"
        )

@router.get("/{reference_id}")
async def get_gst_cibil_report_by_reference_id(
    reference_id: str,
    db: Database = Depends(get_leads_gst_cibil_database),
):
    """
    Get detailed GST & CIBIL report by reference_id
    """
    try:
        doc = db["reports"].find_one({"reference_id": reference_id})
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Report with reference_id '{reference_id}' not found",
            )

        doc["_id"] = str(doc["_id"])

        return {
            "code": "SUCCESS",
            "message": "Report details fetched successfully",
            "data": doc,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Error fetching GST CIBIL report for reference_id %s: %s",
            reference_id,
            e,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch report details: {str(e)}"
        )

