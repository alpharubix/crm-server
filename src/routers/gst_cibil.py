import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.database import Database

from src.database import get_leads_gst_cibil_database

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gst-cibil-reports", tags=["GST & CIBIL Reports"])


@router.get("")
async def get_gst_cibil_reports(
    db: Database = Depends(get_leads_gst_cibil_database),
    search: Optional[str] = Query(None, description="Search by GSTIN or Trade Name"),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
):
    """
    Get all reports from leads_gst_cibil_report.reports collection
    """
    try:
        query = {}
        if search and search.strip():
            term = search.strip()
            query = {
                "$or": [
                    {"gstin": {"$regex": term, "$options": "i"}},
                    {"report.entity.trade_name": {"$regex": term, "$options": "i"}},
                    {"report.entity.legal_name": {"$regex": term, "$options": "i"}},
                    {"reference_id": {"$regex": term, "$options": "i"}},
                ]
            }

        cursor = (
            db["reports"]
            .find(
                query,
                {
                    "_id": 1,
                    "gstin": 1,
                    "reference_id": 1,
                    "report.entity.trade_name": 1,
                    "report.entity.legal_name": 1,
                    "report.entity.mobile": 1,
                    "report.entity.status": 1,
                    "report.bureau.rating": 1,
                    "report.report.generated_at": 1,
                },
            )
            .sort("_id", -1)
            .skip(skip)
            .limit(limit)
        )

        results = []
        for doc in cursor:
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
                    "bureau_rating": bureau.get("rating") or "Not Available",
                    "last_updated": meta.get("generated_at") or "N/A",
                }
            )

        total_count = db["reports"].count_documents(query)

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

