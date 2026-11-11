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

@router.get("/tracker")
async def get_gst_reference_tracker(
    db: Database = Depends(get_leads_gst_cibil_database),
    search: Optional[str] = Query(None, description="Search by GSTIN or Reference ID"),
    status: Optional[str] = Query(None, description="Filter by report_status"),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
):
    """
    Get all uploaded GST numbers status from gst_reference_tracker collection
    """
    try:
        query = {}
        conditions = []

        if search and search.strip():
            escaped_term = re.escape(search.strip())
            conditions.append({
                "$or": [
                    {"gstin": {"$regex": escaped_term, "$options": "i"}},
                    {"reference_id": {"$regex": escaped_term, "$options": "i"}},
                ]
            })

        if status and status.strip() and status.upper() != "ALL":
            conditions.append({"report_status": status.strip()})

        if conditions:
            query = {"$and": conditions} if len(conditions) > 1 else conditions[0]

        cursor = (
            db["gst_reference_tracker"]
            .find(query)
            .sort("_id", -1)
            .skip(skip)
            .limit(limit)
        )

        results = []
        for doc in cursor:
            created_at_val = doc.get("created_at")
            updated_at_val = doc.get("updated_at")
            completed_at_val = doc.get("completed_at")

            # Extract any human-readable error if present
            last_err = doc.get("last_error")
            err_msg = None
            if isinstance(last_err, dict):
                err_msg = last_err.get("error") or str(last_err)
            elif last_err:
                err_msg = str(last_err)

            # Check if lifecycle events have error
            if not err_msg and doc.get("lifecycle_events"):
                events = doc.get("lifecycle_events") or []
                for ev in reversed(events):
                    if ev.get("error"):
                        ev_err = ev.get("error")
                        if isinstance(ev_err, dict) and ev_err.get("error"):
                            err_msg = ev_err.get("error")
                            break
                        elif isinstance(ev_err, str):
                            err_msg = ev_err
                            break

            results.append({
                "id": str(doc["_id"]),
                "gstin": doc.get("gstin") or "",
                "reference_id": doc.get("reference_id") or "",
                "report_status": doc.get("report_status") or "PENDING",
                "request_stage": doc.get("request_stage") or "PENDING",
                "retry_count": doc.get("retry_count", 0),
                "created_at": created_at_val.isoformat() if hasattr(created_at_val, "isoformat") else str(created_at_val or ""),
                "updated_at": updated_at_val.isoformat() if hasattr(updated_at_val, "isoformat") else str(updated_at_val or ""),
                "completed_at": completed_at_val.isoformat() if hasattr(completed_at_val, "isoformat") else str(completed_at_val or ""),
                "error_message": err_msg,
                "source_url": doc.get("source_url"),
                "lifecycle_events": [
                    {
                        "stage": ev.get("stage"),
                        "timestamp": ev.get("timestamp").isoformat() if hasattr(ev.get("timestamp"), "isoformat") else str(ev.get("timestamp") or ""),
                        "details": ev.get("details"),
                        "has_error": bool(ev.get("error")),
                    }
                    for ev in (doc.get("lifecycle_events") or [])
                ],
            })

        total_count = db["gst_reference_tracker"].count_documents(query)

        return {
            "code": "SUCCESS",
            "message": "Reference tracker list fetched successfully",
            "data": results,
            "total": total_count,
        }
    except Exception as e:
        logger.exception("Error fetching GST reference tracker: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch reference tracker: {str(e)}"
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

