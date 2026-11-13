import logging
import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.database import Database
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.database import get_db, get_leads_gst_cibil_database
from src.models.account import Account
from src.models.contact import Contact

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gst-cibil-reports", tags=["GST & CIBIL Reports"])


def extract_last_10_digits(phone_str: Optional[str]) -> Optional[str]:
    if not phone_str:
        return None
    cleaned = re.sub(r"\D", "", str(phone_str))
    if len(cleaned) >= 10:
        return cleaned[-10:]
    return None


@router.get("")
async def get_gst_cibil_reports(
    db: Database = Depends(get_leads_gst_cibil_database),
    sql_db: Session = Depends(get_db),
    search: Optional[str] = Query(None, description="Search by GSTIN or Trade Name"),
    phone: Optional[str] = Query(None, description="Filter by phone number (last 10 digits)"),
    account_id: Optional[int] = Query(None, description="Filter by Account ID"),
    limit: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
):
    """
    Get all reports with report_status mapped from gst_reference_tracker via reference_id,
    and correlate with PostgreSQL Accounts via 10-digit phone number matching.
    """
    # Normalize arguments in case called directly without FastAPI DI
    search = search if isinstance(search, str) else None
    phone = phone if isinstance(phone, str) else None
    account_id = account_id if isinstance(account_id, int) else None
    limit = limit if isinstance(limit, int) else 100
    skip = skip if isinstance(skip, int) else 0

    try:
        search_filter = None
        if search and search.strip():
            escaped_term = re.escape(search.strip())
            search_filter = {
                "$or": [
                    {"gstin": {"$regex": escaped_term, "$options": "i"}},
                    {"report.entity.trade_name": {"$regex": escaped_term, "$options": "i"}},
                    {"report.entity.legal_name": {"$regex": escaped_term, "$options": "i"}},
                    {"reference_id": {"$regex": escaped_term, "$options": "i"}},
                ]
            }

        phone_filter = None
        matched_account_obj = None

        if account_id is not None:
            matched_account_obj = sql_db.query(Account).filter(Account.id == account_id).first()
            if not matched_account_obj:
                return {
                    "code": "SUCCESS",
                    "message": "Account not found",
                    "data": [],
                    "total": 0,
                }

            phones_to_match = set()
            p10 = extract_last_10_digits(matched_account_obj.phone)
            if p10:
                phones_to_match.add(p10)

            contacts = sql_db.query(Contact).filter(Contact.account_id == matched_account_obj.id).all()
            for ct in contacts:
                for raw in (ct.mobile, ct.phone):
                    cp10 = extract_last_10_digits(raw)
                    if cp10:
                        phones_to_match.add(cp10)

            if not phones_to_match:
                return {
                    "code": "SUCCESS",
                    "message": "No phone numbers on account to match",
                    "data": [],
                    "total": 0,
                }

            phone_conditions = [
                {"report.entity.mobile": {"$regex": f"{p}$"}}
                for p in phones_to_match
            ]
            phone_filter = {"$or": phone_conditions} if len(phone_conditions) > 1 else phone_conditions[0]
        elif phone and phone.strip():
            p10 = extract_last_10_digits(phone.strip())
            if p10:
                phone_filter = {"report.entity.mobile": {"$regex": f"{p10}$"}}

        filters = []
        if search_filter:
            filters.append(search_filter)
        if phone_filter:
            filters.append(phone_filter)

        match_stage = {}
        if len(filters) > 1:
            match_stage = {"$and": filters}
        elif len(filters) == 1:
            match_stage = filters[0]

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

        docs = list(db["reports"].aggregate(pipeline))
        total_count = db["reports"].count_documents(match_stage)

        phone_to_account = {}
        if matched_account_obj:
            single_acc_data = {
                "account_id": matched_account_obj.id,
                "account_name": matched_account_obj.account_name,
            }
        else:
            single_acc_data = None
            report_phones_10 = set()
            for doc in docs:
                entity = (doc.get("report") or {}).get("entity") or {}
                m = entity.get("mobile")
                cp = extract_last_10_digits(m)
                if cp:
                    report_phones_10.add(cp)

            if report_phones_10:
                try:
                    acc_conditions = [Account.phone.like(f"%{p}") for p in report_phones_10]
                    matched_accs = sql_db.query(Account.id, Account.account_name, Account.phone).filter(or_(*acc_conditions)).all()
                    for acc in matched_accs:
                        cp = extract_last_10_digits(acc.phone)
                        if cp and cp not in phone_to_account:
                            phone_to_account[cp] = {
                                "account_id": acc.id,
                                "account_name": acc.account_name,
                            }

                    remaining = report_phones_10 - set(phone_to_account.keys())
                    if remaining:
                        ct_conditions = []
                        for p in remaining:
                            ct_conditions.extend([Contact.mobile.like(f"%{p}"), Contact.phone.like(f"%{p}")])
                        if ct_conditions:
                            matched_contacts = (
                                sql_db.query(Contact.mobile, Contact.phone, Account.id, Account.account_name)
                                .select_from(Contact)
                                .join(Account, Contact.account_id == Account.id)
                                .filter(or_(*ct_conditions))
                                .all()
                            )
                            for ct in matched_contacts:
                                for raw in (ct.mobile, ct.phone):
                                    cp = extract_last_10_digits(raw)
                                    if cp and cp not in phone_to_account:
                                        phone_to_account[cp] = {
                                            "account_id": ct.id,
                                            "account_name": ct.account_name,
                                        }
                except Exception as acc_e:
                    logger.warning("Error resolving account details for reports batch: %s", acc_e)

        results = []
        for doc in docs:
            report_data = doc.get("report") or {}
            entity = report_data.get("entity") or {}
            bureau = report_data.get("bureau") or {}
            meta = report_data.get("report") or {}

            raw_mobile = entity.get("mobile") or ""
            clean_m = extract_last_10_digits(raw_mobile)

            if single_acc_data:
                acc_info = single_acc_data
            else:
                acc_info = phone_to_account.get(clean_m) if clean_m else None

            results.append(
                {
                    "id": str(doc["_id"]),
                    "gstin": doc.get("gstin") or entity.get("gstin") or "",
                    "name": entity.get("trade_name") or entity.get("legal_name") or "N/A",
                    "contact_number": raw_mobile or "N/A",
                    "reference_id": doc.get("reference_id") or "",
                    "entity_status": entity.get("status") or "Active",
                    "report_status": doc.get("tracker_report_status") or "PENDING",
                    "request_stage": doc.get("tracker_request_stage") or "PENDING",
                    "bureau_rating": bureau.get("rating") or "Not Available",
                    "last_updated": meta.get("generated_at") or "N/A",
                    "account_id": acc_info["account_id"] if acc_info else None,
                    "account_name": acc_info["account_name"] if acc_info else "No Account",
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
    sql_db: Session = Depends(get_db),
):
    """
    Get detailed GST & CIBIL report by reference_id and correlate with PostgreSQL Account
    """
    try:
        doc = db["reports"].find_one({"reference_id": reference_id})
        if not doc:
            raise HTTPException(
                status_code=404,
                detail=f"Report with reference_id '{reference_id}' not found",
            )

        doc["_id"] = str(doc["_id"])

        entity = (doc.get("report") or {}).get("entity") or {}
        raw_mobile = entity.get("mobile") or ""
        clean_mobile = extract_last_10_digits(raw_mobile)

        account_info = None
        if clean_mobile:
            try:
                matched_acc = (
                    sql_db.query(Account.id, Account.account_name)
                    .filter(Account.phone.like(f"%{clean_mobile}"))
                    .first()
                )
                if matched_acc:
                    account_info = {
                        "account_id": matched_acc.id,
                        "account_name": matched_acc.account_name,
                    }
                else:
                    matched_ct = (
                        sql_db.query(Account.id, Account.account_name)
                        .select_from(Account)
                        .join(Contact, Contact.account_id == Account.id)
                        .filter(or_(Contact.mobile.like(f"%{clean_mobile}"), Contact.phone.like(f"%{clean_mobile}")))
                        .first()
                    )
                    if matched_ct:
                        account_info = {
                            "account_id": matched_ct.id,
                            "account_name": matched_ct.account_name,
                        }
            except Exception as acc_err:
                logger.warning("Error resolving account for phone %s: %s", clean_mobile, acc_err)

        doc["account_id"] = account_info["account_id"] if account_info else None
        doc["account_name"] = account_info["account_name"] if account_info else "No Account"

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

