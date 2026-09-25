import logging
import math
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.database import Database
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.database import get_db, get_mongodb

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Tele CRM"])


def clean_text(val: Any) -> str:
    s = str(val or "").strip()
    return "" if s.lower() in ("undefined", "null", "none") else s


def parse_filter_datetime(dt_str: str | None, is_end_of_day: bool = False) -> datetime | None:
    if not dt_str or not str(dt_str).strip():
        return None
    s = str(dt_str).strip()
    try:
        if "T" in s and ("+" in s or "-" in s[10:] or "Z" in s):
            clean_s = s.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_s)
            return dt.astimezone(UTC).replace(tzinfo=None)

        s_clean = s.replace("T", " ")
        if len(s_clean) == 10:  # YYYY-MM-DD
            s_full = f"{s_clean} 23:59:59" if is_end_of_day else f"{s_clean} 00:00:00"
        elif len(s_clean) == 16:  # YYYY-MM-DD HH:MM
            s_full = f"{s_clean}:59" if is_end_of_day else f"{s_clean}:00"
        elif len(s_clean) >= 19:  # YYYY-MM-DD HH:MM:SS
            s_full = s_clean[:19]
        else:
            return None

        dt_local = datetime.strptime(s_full, "%Y-%m-%d %H:%M:%S")
        # Treat as IST (UTC+05:30), convert to naive UTC datetime
        return dt_local - timedelta(hours=5, minutes=30)
    except Exception as e:
        logger.warning("Error parsing filter datetime %s: %s", dt_str, e)
        return None


def normalize_call_type_str(act_type: Any) -> str:
    s = str(act_type or "").lower().strip()
    if "miss" in s:
        return "missed"
    if "incom" in s or "received" in s:
        return "incoming"
    if "out" in s or "dial" in s:
        return "outgoing"
    return "outgoing"


def calculate_relative_time(raw_ts: Any) -> str:
    if not raw_ts:
        return ""
    try:
        now = datetime.now(UTC)
        if isinstance(raw_ts, datetime):
            dt = raw_ts if raw_ts.tzinfo else raw_ts.replace(tzinfo=UTC)
        elif isinstance(raw_ts, str):
            clean_str = raw_ts.replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(clean_str)
            except Exception:
                dt = datetime.strptime(clean_str, "%d/%m/%Y %H:%M:%S").replace(
                    tzinfo=UTC
                )
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
        else:
            return ""
        diff = now - dt
        diff_sec = int(diff.total_seconds())
        if diff_sec < 0:
            return "Just now"
        if diff_sec < 60:
            return f"{diff_sec}s"
        diff_min = diff_sec // 60
        if diff_min < 60:
            return f"{diff_min}m"
        diff_hours = diff_min // 60
        if diff_hours < 24:
            return f"{diff_hours}h"
        diff_days = diff_hours // 24
        if diff_days < 30:
            return f"{diff_days}d"
        diff_months = diff_days // 30
        if diff_months < 12:
            return f"{diff_months}mo"
        return f"{diff_months // 12}y"
    except Exception:
        return ""


# @router.post("/telecrm/sync-all")
# def sync_all_telecrm(
#     mongo_db: Database = Depends(get_mongodb),
# ):
#     try:
#         result = sync_all_telecrm_leads(mongo_db)
#         return result
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=str(e),
#         )


# @router.post("/telecrm/sync-yesterday")
# def sync_yesterday_telecrm(
#     target_date: date | None = Query(
#         default=None,
#         description="Optional date (YYYY-MM-DD) to sync. Defaults to yesterday.",
#     ),
#     mongo_db: Database = Depends(get_mongodb),
# ):
#     try:
#         result = sync_yesterday_telecrm_leads(
#             target_date=target_date,
#             mongo_db=mongo_db,
#         )
#         return result
#     except Exception as e:
#         raise HTTPException(
#             status_code=500,
#             detail=str(e),
#         )


@router.post("/call-details")
def add_call_details(
    payload: dict[str, Any],
    mongo_db: Database = Depends(get_mongodb),
):
    try:
        doc = payload.copy()
        doc["created_at"] = datetime.now(UTC)

        result = mongo_db["test-tele-crm"].insert_one(doc)
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
            detail=f"Failed to save call details: {e!s}",
        )


@router.get("/call-details")
def get_telecrm_activities(
    phone: str = Query(..., description="Account phone number to look up"),
    mongo_db: Database = Depends(get_mongodb),
):
    try:
        raw_phone = str(phone or "").strip()
        clean_digits = "".join(filter(str.isdigit, raw_phone))
        phone_10 = clean_digits[-10:] if len(clean_digits) >= 10 else clean_digits
        if not phone_10:
            return {
                "status": "success",
                "count": 0,
                "data": [],
            }

        q_filters: list[dict[str, Any]] = [
            {"lead_phone": {"$regex": f"{phone_10}$"}},
            {"phone": {"$regex": f"{phone_10}$"}},
        ]
        if phone_10.isdigit():
            q_filters.append({"lead_phone": int(phone_10)})
            q_filters.append({"phone": int(phone_10)})

        coll = mongo_db["test-tele-crm"]
        call_docs = list(
            coll.find({"$or": q_filters}).sort([("created_at", -1), ("_id", -1)])
        )

        activities = []
        for doc in call_docs:
            doc_id = str(doc.get("_id", ""))
            lead_id = clean_text(doc.get("lead_id"))
            telecrm_url = (
                f"https://next.telecrm.in/6a8c537f3aeed414e38866a5/views/all-leads-v2/overlay/l/{lead_id}"
                if lead_id
                else None
            )

            raw_type = doc.get("call_type") or doc.get("type") or "Outgoing Call"
            c_type = normalize_call_type_str(raw_type)

            raw_duration = clean_text(doc.get("duration")) or "0"
            dur_str = (
                f"{raw_duration}s" if not raw_duration.endswith("s") else raw_duration
            )

            call_recording_url = (
                clean_text(doc.get("call_recording_url")) or telecrm_url or ""
            )
            creation_timestamp = clean_text(doc.get("creation_timestamp"))
            created_at_val = doc.get("created_at")
            if isinstance(created_at_val, datetime):
                created_at_str = created_at_val.isoformat()
            else:
                created_at_str = clean_text(created_at_val)

            display_ts = creation_timestamp or created_at_str

            actor_employee_email = (
                clean_text(doc.get("actor_employee_email"))
                or clean_text(doc.get("my_name"))
                or ""
            )
            lead_name = clean_text(doc.get("lead_name"))
            lead_phone = clean_text(doc.get("lead_phone")) or clean_text(
                doc.get("phone")
            )
            call_status = clean_text(doc.get("status")) or "Yet to be Dialed"
            callback_dt = clean_text(doc.get("call_back_date_time"))
            call_note = clean_text(doc.get("call_note"))
            user_note_text = call_note or clean_text(doc.get("user_note"))
            system_note_text = clean_text(doc.get("system_note"))

            rel_time = calculate_relative_time(created_at_val or creation_timestamp)

            item = {
                "id": doc_id,
                "telecrm_url": telecrm_url,
                "relative_time": rel_time or "1d",
                "call_action": {
                    "type": c_type,
                    "duration": dur_str,
                    "creation_timestamp": display_ts,
                    "feedback": call_status,
                    "call_recording_url": call_recording_url,
                    "actor_employee_email": actor_employee_email,
                },
                "leads": {
                    "lead_id": lead_id,
                    "name": lead_name,
                    "alternate_phone": lead_phone,
                    "status": call_status,
                    "callback_date_time": callback_dt or None,
                    "lead_assignee": clean_text(doc.get("my_name")),
                    "assignee_email": actor_employee_email,
                },
                "status": call_status,
                "user_note": {
                    "text": user_note_text,
                    "actor_employee_email": actor_employee_email,
                },
                "system_note": {
                    "text": system_note_text,
                },
                # Flat properties directly from test-tele-crm
                "lead_name": lead_name,
                "lead_phone": lead_phone,
                "lead_id": lead_id,
                "call_type": raw_type,
                "status": call_status,
                "call_back_date_time": callback_dt,
                "my_name": clean_text(doc.get("my_name")),
                "creation_timestamp": display_ts,
                "call_recording_url": call_recording_url,
                "call_note": call_note,
                "duration": raw_duration,
                "actor_employee_email": actor_employee_email,
                "type": raw_type,
                "created_at": created_at_str,
            }
            activities.append(item)

        return {
            "status": "success",
            "count": len(activities),
            "data": activities,
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch call details: {e!s}",
        )


@router.get("/recordings")
@router.get("/call-recordings")
def get_call_recordings_list(
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    search: str | None = Query(
        default=None,
        description="Search account name, lead name, phone number, or employee email",
    ),
    call_type: str | None = Query(
        default=None,
        description="Filter by call type: all, outgoing, incoming, missed",
    ),
    user: str | None = Query(
        default=None,
        description="Filter by user email / caller",
    ),
    from_date: str | None = Query(
        default=None,
        description="Start date or datetime (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)",
    ),
    to_date: str | None = Query(
        default=None,
        description="End date or datetime (YYYY-MM-DD or YYYY-MM-DD HH:MM:SS)",
    ),
    db: Session = Depends(get_db),
    mongo_db: Database = Depends(get_mongodb),
):
    try:
        filter_conditions: list[dict[str, Any]] = []

        # 1. Call type filter
        if call_type and call_type.strip().lower() not in ("all", ""):
            c_lower = call_type.strip().lower()
            if "miss" in c_lower:
                filter_conditions.append(
                    {
                        "$or": [
                            {"call_type": {"$regex": "miss", "$options": "i"}},
                            {"type": {"$regex": "miss", "$options": "i"}},
                        ]
                    }
                )
            elif "incom" in c_lower or "rec" in c_lower or c_lower == "incoming":
                filter_conditions.append(
                    {
                        "$or": [
                            {"call_type": {"$regex": "incom|received", "$options": "i"}},
                            {"type": {"$regex": "incom|received", "$options": "i"}},
                        ]
                    }
                )
            elif "out" in c_lower or "dial" in c_lower or c_lower == "outgoing":
                filter_conditions.append(
                    {
                        "$or": [
                            {"call_type": {"$regex": "out|dial", "$options": "i"}},
                            {"type": {"$regex": "out|dial", "$options": "i"}},
                        ]
                    }
                )
            else:
                filter_conditions.append(
                    {
                        "$or": [
                            {"call_type": {"$regex": c_lower, "$options": "i"}},
                            {"type": {"$regex": c_lower, "$options": "i"}},
                        ]
                    }
                )

        # 2. Search query filter
        if search and search.strip():
            s = search.strip()
            s_clean_digits = "".join(filter(str.isdigit, s))
            search_or: list[dict[str, Any]] = [
                {"lead_name": {"$regex": s, "$options": "i"}},
                {"lead_phone": {"$regex": s, "$options": "i"}},
                {"phone": {"$regex": s, "$options": "i"}},
                {"actor_employee_email": {"$regex": s, "$options": "i"}},
                {"my_name": {"$regex": s, "$options": "i"}},
            ]

            if s_clean_digits:
                search_or.append({"lead_phone": {"$regex": f"{s_clean_digits[-10:]}$"}})
                search_or.append({"phone": {"$regex": f"{s_clean_digits[-10:]}$"}})

            # Also search accounts_merged for matching account_name
            try:
                acc_query = text("""
                    SELECT RIGHT(REGEXP_REPLACE(phone, '[^0-9]', '', 'g'), 10) as phone_10
                    FROM accounts_merged
                    WHERE account_name ILIKE :search
                    LIMIT 50
                """)
                matching_acc_rows = db.execute(
                    acc_query, {"search": f"%{s}%"}
                ).fetchall()
                acc_phones = [r.phone_10 for r in matching_acc_rows if r.phone_10]
                for p10 in acc_phones:
                    search_or.append({"lead_phone": {"$regex": f"{p10}$"}})
                    search_or.append({"phone": {"$regex": f"{p10}$"}})
            except Exception as search_err:
                logger.warning(
                    "Error searching accounts in tele-crm recordings: %s", search_err
                )

            filter_conditions.append({"$or": search_or})

        # 3. User filter
        if user and user.strip().lower() not in ("all", ""):
            u_clean = user.strip()
            prefix = u_clean.split("@")[0] if "@" in u_clean else u_clean
            filter_conditions.append({
                "$or": [
                    {"actor_employee_email": {"$regex": f"^{prefix}", "$options": "i"}},
                    {"my_name": {"$regex": f"^{prefix}", "$options": "i"}},
                    {"actor_employee_email": {"$regex": u_clean, "$options": "i"}},
                ]
            })

        # 4. Period / Date & Time range filter
        created_at_filter: dict[str, Any] = {}
        start_utc = parse_filter_datetime(from_date, is_end_of_day=False)
        if start_utc:
            created_at_filter["$gte"] = start_utc

        end_utc = parse_filter_datetime(to_date, is_end_of_day=True)
        if end_utc:
            created_at_filter["$lte"] = end_utc

        if created_at_filter:
            filter_conditions.append({"created_at": created_at_filter})

        mongo_query = {"$and": filter_conditions} if filter_conditions else {}

        coll = mongo_db["test-tele-crm"]
        total_count = coll.count_documents(mongo_query)
        total_pages = math.ceil(total_count / limit) if total_count > 0 else 1

        skip = (page - 1) * limit
        cursor = (
            coll.find(mongo_query)
            .sort([("created_at", -1), ("_id", -1)])
            .skip(skip)
            .limit(limit)
        )
        call_docs = list(cursor)

        # 3. Extract 10-digit phones for the current batch
        doc_phone_10_map: dict[str, str] = {}
        for doc in call_docs:
            raw_p = str(doc.get("lead_phone") or doc.get("phone") or "").strip()
            clean_digits = "".join(filter(str.isdigit, raw_p))
            p10 = clean_digits[-10:] if len(clean_digits) >= 10 else clean_digits
            if p10:
                doc_phone_10_map[str(doc["_id"])] = p10

        distinct_10 = list(set(doc_phone_10_map.values()))
        account_map: dict[str, dict[str, Any]] = {}
        if distinct_10:
            acc_sql = text("""
                SELECT id, account_name, RIGHT(REGEXP_REPLACE(phone, '[^0-9]', '', 'g'), 10) AS phone_10
                FROM accounts_merged
                WHERE RIGHT(REGEXP_REPLACE(phone, '[^0-9]', '', 'g'), 10) IN :phones
            """)
            rows = db.execute(acc_sql, {"phones": tuple(distinct_10)}).fetchall()
            for r in rows:
                if r.phone_10 not in account_map or (
                    not account_map[r.phone_10]["account_name"] and r.account_name
                ):
                    account_map[r.phone_10] = {
                        "id": r.id,
                        "account_name": r.account_name or "",
                    }

        # 4. Build output list
        recordings = []
        for doc in call_docs:
            doc_id = str(doc.get("_id", ""))
            p10 = doc_phone_10_map.get(doc_id)
            acc_info = account_map.get(p10) if p10 else None

            lead_id = clean_text(doc.get("lead_id"))
            telecrm_url = (
                f"https://next.telecrm.in/6a8c537f3aeed414e38866a5/views/all-leads-v2/overlay/l/{lead_id}"
                if lead_id
                else (
                    f"https://next.telecrm.in/6a8c537f3aeed414e38866a5/views/all-leads-v2?search={doc.get('lead_phone') or ''}"
                    if doc.get("lead_phone")
                    else None
                )
            )

            raw_type = doc.get("call_type") or doc.get("type") or "Outgoing Call"
            c_type = normalize_call_type_str(raw_type)

            raw_duration = clean_text(doc.get("duration")) or "0"
            call_recording_url = clean_text(doc.get("call_recording_url"))
            creation_timestamp = clean_text(doc.get("creation_timestamp"))
            created_at_val = doc.get("created_at")
            if isinstance(created_at_val, datetime):
                created_at_str = created_at_val.isoformat()
            else:
                created_at_str = clean_text(created_at_val)

            display_ts = creation_timestamp or created_at_str

            actor_employee_email = (
                clean_text(doc.get("actor_employee_email"))
                or clean_text(doc.get("my_name"))
                or ""
            )
            lead_name = clean_text(doc.get("lead_name"))
            lead_phone = clean_text(doc.get("lead_phone")) or clean_text(
                doc.get("phone")
            )
            call_status = clean_text(doc.get("status")) or "Yet to be Dialed"
            callback_dt = clean_text(doc.get("call_back_date_time"))
            call_note = clean_text(doc.get("call_note"))

            recordings.append(
                {
                    "id": doc_id,
                    "account_id": str(acc_info["id"]) if acc_info else None,
                    "account_name": acc_info["account_name"] if acc_info else None,
                    "telecrm_name": lead_name,
                    "lead_id": lead_id,
                    "telecrm_url": telecrm_url,
                    "lead_phone": lead_phone,
                    "call_type": raw_type,
                    "normalized_call_type": c_type,
                    "actor_employee_email": actor_employee_email,
                    "creation_timestamp": display_ts,
                    "created_at": created_at_str,
                    "relative_time": calculate_relative_time(
                        created_at_val or creation_timestamp
                    ),
                    "duration": raw_duration,
                    "call_recording_url": call_recording_url,
                    "call_note": call_note,
                    "status": call_status,
                    "call_back_date_time": callback_dt,
                }
            )

        return {
            "status": "success",
            "data": recordings,
            "pagination": {
                "total": total_count,
                "page": page,
                "limit": limit,
                "total_pages": total_pages,
            },
        }
    except Exception as e:
        logger.exception("Failed to fetch call recordings")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch call recordings: {e!s}",
        )
