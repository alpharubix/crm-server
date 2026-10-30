import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, File, UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, selectinload

from src.controllers.audit_log import log_action
from src.controllers.auth import MANAGERID
from src.controllers.notes import get_notes
from src.database import get_db, get_mongodb

from src.models.account import Account
from src.models.deal import Deal
from src.models.ticket import Ticket, TicketStatusHistory


def format_ticket_duration_short(seconds: int) -> str:
    if not seconds or seconds < 0:
        return "0m"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60

    if days > 0:
        return f"{days}d"
    elif hours > 0:
        return f"{hours}h"
    else:
        return f"{minutes}m"


def get_ticket_status_color(status: str) -> str:
    s = (status or "").lower()
    if "approved" in s or "disbursed" in s or "success" in s:
        return "emerald"
    if "review" in s or "credit" in s or "assessment" in s:
        return "blue"
    if "login" in s or "fresh" in s or "spillover" in s:
        return "amber"
    if "rejected" in s or "not interested" in s or "disapproved" in s:
        return "rose"
    return "blue"


def build_batch_ticket_status_journeys(db: Session, ticket_ids: list[int]):
    if not ticket_ids:
        return {}
    now_dt = datetime.now(timezone.utc)

    # 1. Fetch ticket basic info
    tickets_info = (
        db.query(Ticket.id, Ticket.created_at, Ticket.ticket_status)
        .filter(Ticket.id.in_(ticket_ids))
        .all()
    )
    ticket_info_map = {t.id: t for t in tickets_info}

    # 2. Auto-repair/backfill any ticket that has history records but missed the initial record from created_at
    try:
        from src.models.audit_log import AuditLog

        existing_histories = (
            db.query(TicketStatusHistory)
            .filter(TicketStatusHistory.ticket_id.in_(ticket_ids))
            .order_by(TicketStatusHistory.ticket_id, TicketStatusHistory.start_time.asc())
            .all()
        )

        histories_by_ticket: dict[int, list[TicketStatusHistory]] = {tid: [] for tid in ticket_ids}
        for h in existing_histories:
            histories_by_ticket[h.ticket_id].append(h)

        repaired = False
        for tid, h_list in histories_by_ticket.items():
            if not h_list:
                continue
            t_obj = ticket_info_map.get(tid)
            if not t_obj or not t_obj.created_at:
                continue

            first_h = h_list[0]
            c_time = t_obj.created_at
            if c_time.tzinfo is None:
                c_time = c_time.replace(tzinfo=timezone.utc)
            f_start = first_h.start_time
            if f_start and f_start.tzinfo is None:
                f_start = f_start.replace(tzinfo=timezone.utc)

            if f_start and (f_start - c_time).total_seconds() > 60:
                initial_st = "Yet to Lender Login"
                audit = (
                    db.query(AuditLog)
                    .filter(
                        AuditLog.entity == "Ticket",
                        AuditLog.entity_id == tid,
                        AuditLog.action == "CREATED",
                    )
                    .first()
                )
                if audit and isinstance(audit.payload, dict) and audit.payload.get("ticket_status"):
                    initial_st = audit.payload["ticket_status"]
                elif first_h.status == "Yet to Lender Login":
                    initial_st = "Yet to Lender Login"

                gap_secs = max(int((f_start - c_time).total_seconds()), 0)
                backfilled_rec = TicketStatusHistory(
                    ticket_id=tid,
                    company_id=1,
                    status=initial_st,
                    start_time=c_time,
                    end_time=f_start,
                    duration_seconds=gap_secs,
                    total_time_stayed=format_ticket_duration_short(gap_secs),
                    moved_by_id=first_h.moved_by_id,
                )
                db.add(backfilled_rec)
                repaired = True

        if repaired:
            db.commit()
    except Exception as rep_err:
        db.rollback()
        import logging
        logging.getLogger(__name__).warning(f"Error repairing ticket status history: {rep_err}")

    history_records = (
        db.query(TicketStatusHistory)
        .filter(TicketStatusHistory.ticket_id.in_(ticket_ids))
        .options(selectinload(TicketStatusHistory.moved_by_user))
        .order_by(TicketStatusHistory.ticket_id, TicketStatusHistory.start_time.asc())
        .all()
    )

    journeys_by_ticket = {tid: [] for tid in ticket_ids}
    for rec in history_records:
        user_name = "System"
        if rec.moved_by_user:
            user_name = (
                rec.moved_by_user.full_name or rec.moved_by_user.email or "System"
            )

        st_name = rec.status or "Yet to Lender Login"
        start_dt = rec.start_time
        if start_dt and start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=timezone.utc)

        start_str = start_dt.strftime("%Y-%m-%d") if start_dt else ""

        if rec.end_time:
            end_dt = rec.end_time
            if end_dt and end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            end_str = end_dt.strftime("%Y-%m-%d") if end_dt else ""
            dur_secs = rec.duration_seconds or (
                max(int((end_dt - start_dt).total_seconds()), 0)
                if (end_dt and start_dt)
                else 0
            )
        else:
            end_str = "Present"
            dur_secs = (
                max(int((now_dt - start_dt).total_seconds()), 0) if start_dt else 0
            )

        item = {
            "name": st_name,
            "duration": format_ticket_duration_short(dur_secs),
            "color": get_ticket_status_color(st_name),
            "startDate": start_str,
            "endDate": end_str,
            "updatedBy": user_name,
        }
        if rec.ticket_id in journeys_by_ticket:
            journeys_by_ticket[rec.ticket_id].append(item)

    # Fallback for tickets with no history entries yet
    missing_ids = [tid for tid, items in journeys_by_ticket.items() if not items]
    if missing_ids:
        missing_tickets = (
            db.query(Ticket.id, Ticket.ticket_status, Ticket.created_at)
            .filter(Ticket.id.in_(missing_ids))
            .all()
        )
        for m_ticket in missing_tickets:
            st_name = m_ticket.ticket_status or "Yet to Lender Login"
            c_time = m_ticket.created_at
            if c_time and c_time.tzinfo is None:
                c_time = c_time.replace(tzinfo=timezone.utc)
            dur_secs = max(int((now_dt - c_time).total_seconds()), 0) if c_time else 0
            start_str = c_time.strftime("%Y-%m-%d") if c_time else ""
            journeys_by_ticket[m_ticket.id] = [
                {
                    "name": st_name,
                    "duration": format_ticket_duration_short(dur_secs),
                    "color": get_ticket_status_color(st_name),
                    "startDate": start_str,
                    "endDate": "Present",
                    "updatedBy": "System",
                }
            ]

    return journeys_by_ticket


tickets_router = APIRouter(prefix="/tickets", tags=["tickets"])


# Helper function to format the database model into a dictionary
def format_ticket(t: Ticket) -> dict:
    data = {c.name: getattr(t, c.name) for c in t.__table__.columns}
    for key in (
        "id",
        "deal_id",
        "account_id",
        "created_by",
        "modified_by",
    ):
        if data.get(key) is not None:
            data[key] = str(data[key])

    # Dynamic lookup via Foreign Keys (account_id & deal_id)
    # Ensures if Account name is updated, Tickets dynamically return the updated name
    if t.account and t.account.account_name:
        data["account_name"] = t.account.account_name
    elif t.deal and t.deal.account and t.deal.account.account_name:
        data["account_name"] = t.deal.account.account_name
    elif t.deal and getattr(t.deal, "account_name", None):
        data["account_name"] = t.deal.account_name
    else:
        data["account_name"] = "-"

    if t.deal and t.deal.deal_name:
        data["deal_name"] = t.deal.deal_name

    data["deal_owner_id"] = (
        str(t.deal.deal_owner_id) if t.deal and t.deal.deal_owner_id else None
    )
    data["partner_name"] = getattr(t, "partner_name", None)
    data["modified_at"] = t.updated_at
    data["modified_time"] = t.updated_at
    return data


@tickets_router.get("")
@tickets_router.get("/")
def get_tickets_list(
    request: Request,
    db: Session = Depends(get_db),
    page: int = 1,
    deal_id: int | None = None,
    kanban: bool = False,
    created_from: str | None = None,
    created_to: str | None = None,
    ticket_status: list[str] | None = Query(default=None),
    type_of_loan: str | None = None,
    account_name: str | None = None,
    lender_login_from: str | None = None,
    lender_login_to: str | None = None,
    deal_owner_id: int | None = None,
    targeted_disbursement_from: str | None = None,
    targeted_disbursement_to: str | None = None,
    disbursement_from: str | None = None,
    disbursement_to: str | None = None,
):

    MANAGER_EXECUTIVES_MAP = MANAGERID.MANAGER_EXECUTIVES_MAP
    user_id = request.state.user_id
    user_role = request.state.role

    allowed_owner_ids = None
    if int(user_id) in MANAGERID.BYPASS_USER_IDS:
        pass
    elif user_role == "manager":
        allowed_owner_ids = [user_id] + MANAGER_EXECUTIVES_MAP.get(user_id, [])
    elif user_role == "executive":
        allowed_owner_ids = [user_id]

    filters = []

    from src.utility.archive_visibility import active_ticket_condition
    filters.append(active_ticket_condition())

    if deal_id:
        filters.append(Ticket.deal_id == deal_id)
    if ticket_status:
        statuses = [s.strip() for s in (ticket_status if isinstance(ticket_status, list) else [ticket_status]) if s and s.strip()]
        if statuses:
            filters.append(
                or_(*[Ticket.ticket_status.ilike(f"%{s}%") for s in statuses])
            )
    if type_of_loan:
        filters.append(Ticket.type_of_loan.ilike(f"%{type_of_loan.strip()}%"))

    # ------------------- APPLY GLOBAL FILTERS -------------------
    # Dates
    if created_from:
        try:
            date_from = datetime.strptime(created_from, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            filters.append(Ticket.created_at >= date_from)
        except ValueError:
            pass
    if created_to:
        try:
            date_to = (
                datetime.strptime(created_to, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                + timedelta(days=1)
                - timedelta(seconds=1)
            )
            filters.append(Ticket.created_at <= date_to)
        except ValueError:
            pass

    if lender_login_from:
        try:
            d_from = datetime.strptime(lender_login_from, "%Y-%m-%d").date()
            filters.append(Ticket.lender_login_date >= d_from)
        except ValueError:
            pass
    if lender_login_to:
        try:
            d_to = datetime.strptime(lender_login_to, "%Y-%m-%d").date()
            filters.append(Ticket.lender_login_date <= d_to)
        except ValueError:
            pass

    if targeted_disbursement_from:
        try:
            d_from = datetime.strptime(targeted_disbursement_from, "%Y-%m-%d").date()
            filters.append(Ticket.targeted_disbursement_date >= d_from)
        except ValueError:
            pass
    if targeted_disbursement_to:
        try:
            d_to = datetime.strptime(targeted_disbursement_to, "%Y-%m-%d").date()
            filters.append(Ticket.targeted_disbursement_date <= d_to)
        except ValueError:
            pass

    if disbursement_from:
        try:
            d_from = datetime.strptime(disbursement_from, "%Y-%m-%d").date()
            filters.append(Ticket.disbursement_date >= d_from)
        except ValueError:
            pass
    if disbursement_to:
        try:
            d_to = datetime.strptime(disbursement_to, "%Y-%m-%d").date()
            filters.append(Ticket.disbursement_date <= d_to)
        except ValueError:
            pass

    # Relationships filters
    if allowed_owner_ids is not None:
        filters.append(
            or_(
                Deal.deal_owner_id.in_(allowed_owner_ids),
                Account.account_owner_id.in_(allowed_owner_ids),
            )
        )
    if deal_owner_id:
        filters.append(Deal.deal_owner_id == deal_owner_id)
    if account_name:
        filters.append(Deal.account_name.ilike(f"%{account_name.strip()}%"))

    # Build the final unified query structure
    final_query = (
        db.query(Ticket)
        .join(Deal, Ticket.deal_id == Deal.id)
        .outerjoin(Account, Deal.account_id == Account.id)
        .filter(and_(*filters))
    )

    if kanban:
        # 1. Get the real total count based on ALL combined filters (Can be > 200)
        total_count = final_query.count()

        # 2. Fetch the data, but CAP it at 200 items max directly in the database
        tickets = (
            final_query.options(selectinload(Ticket.deal), selectinload(Ticket.account))
            .limit(200)
            .all()
        )

        # 3. Group your dataset by ticket status
        grouped_data = {}
        for t in tickets:
            status = t.ticket_status or "No Status"
            ticket_dict = format_ticket(t)
            grouped_data.setdefault(status, []).append(ticket_dict)

        # 4. Return matching the exact Deals structure perfectly
        return {"data": grouped_data, "page_info": {"total": total_count}}

    # Standard list view
    limit = 100
    offset = (page - 1) * limit

    total = final_query.count()
    tickets = (
        final_query.options(selectinload(Ticket.deal), selectinload(Ticket.account))
        .order_by(Ticket.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    total_pages = math.ceil(total / limit) if limit > 0 else 1
    t_ids = [t.id for t in tickets]
    journeys_map = build_batch_ticket_status_journeys(db, t_ids)

    result_data = []
    for t in tickets:
        item = format_ticket(t)
        j_list = journeys_map.get(t.id, [])
        item["status_journey"] = j_list
        item["journey"] = j_list
        result_data.append(item)

    return {
        "data": result_data,
        "page_info": {
            "page": page, 
            "total_pages": total_pages, 
            "data_size": total,
            "has_more": page < total_pages
        },
    }


@tickets_router.post("")
@tickets_router.post("/")
async def create_ticket(request: Request, db: Session = Depends(get_db)):
    body = await request.json()

    if "deal_id" not in body:
        raise HTTPException(status_code=400, detail="deal_id is required")

    deal_record = db.query(Deal).filter(Deal.id == int(body["deal_id"])).first()
    if not deal_record:
        raise HTTPException(status_code=404, detail="Deal not found")
    if deal_record.archived_at is not None:
        raise HTTPException(status_code=400, detail="Cannot create ticket under an archived deal")
    if deal_record.account and deal_record.account.archived_at is not None:
        raise HTTPException(status_code=400, detail="Cannot create ticket under an archived account")

    allowed_fields = {
        "deal_id",
        "loan_account_status",
        "ticket_login",
        "lender_name",
        "potential",
        "lender_login_type",
        "lender_login_date",
        "partner_name",
        "targeted_disbursement_date",
        "type_of_loan",
        "disbursement_date",
        "ticket_status",
        "ticket_stage",
        "approved_amount",
        "sanction_amount",
        "processing_fees",
        "disbursed_amount",
        "pf_percentage",
        "tenure",
        "insurance_amount",
        "loan_start_date",
        "rate_of_interest",
        "loan_end_date",
        "interest_type",
        "lender_rejection_reason",
        "lender_rejection_status_explanation",
        "account_id",
        "customer_rejection_reason",
        "customer_rejection_status_explanation",
        "ticket_call_back_datetime",
    }

    if "call_back_date_time" in body and "ticket_call_back_datetime" not in body:
        body["ticket_call_back_datetime"] = body["call_back_date_time"]

    filtered_body = {k: v for k, v in body.items() if k in allowed_fields}

    if "ticket_call_back_datetime" in filtered_body and filtered_body["ticket_call_back_datetime"]:
        val = filtered_body["ticket_call_back_datetime"]
        if isinstance(val, str):
            try:
                val = datetime.fromisoformat(val.replace("Z", "+00:00"))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail={"message": "Invalid datetime format for ticket_call_back_datetime"},
                )
        if hasattr(val, "tzinfo") and val.tzinfo is None:
            val = val.replace(tzinfo=timezone.utc)
        if val < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=400,
                detail={"message": "Date should not be in the past"},
            )
        filtered_body["ticket_call_back_datetime"] = val

    user_id = request.state.user_id
    user_role = request.state.role

    # --- Auto-generate ticket_name: {deal_name}/TK{ticket_id} ---
    deal_id_val = body.get("deal_id")
    if not deal_id_val:
        raise HTTPException(status_code=400, detail="deal_id is required")
    parent_deal = db.query(Deal).filter(Deal.id == int(deal_id_val)).first()
    if not parent_deal:
        raise HTTPException(status_code=404, detail="Parent deal not found")

    # existing_ticket_count = (
    #     db.query(Ticket).filter(Ticket.deal_id == int(deal_id_val)).count()
    # )
    # existing_ticket_count += 1
    # ticket_sequence = str(existing_ticket_count).zfill(4)
    # parent_deal_name = parent_deal.deal_name or parent_deal.account_name or str(deal_id_val)
    # generated_ticket_name = f"{parent_deal_name}/TK{ticket_sequence}"
    # filtered_body["ticket_name"] = generated_ticket_name

    # --- Duplicate ticket check: same deal + lender_name ---
    new_lender_name = body.get("lender_name")
    if new_lender_name and new_lender_name != "Not Applicable":
        duplicate_ticket = (
            db.query(Ticket)
            .filter(
                Ticket.deal_id == int(deal_id_val),
                Ticket.lender_name == new_lender_name,
            )
            .first()
        )
        if duplicate_ticket:
            raise HTTPException(
                status_code=409,
                detail=(
                    'A similar ticket with same "Lender Name" already exist, '
                    'Please try changing the "Lender Name" else refer to the existing tickets'
                ),
            )

    ticket = Ticket(**filtered_body, created_by=user_id)
    db.add(ticket)
    db.flush()

    parent_deal_name = (
        parent_deal.deal_name
        or f"{(parent_deal.account_name or 'ACC').strip()}/DL{parent_deal.id}"
    )
    ticket.ticket_name = f"{parent_deal_name}/TK{ticket.id}"

    now_time = datetime.now(timezone.utc)
    st_val = ticket.ticket_status or "Yet to Lender Login"
    t_history = TicketStatusHistory(
        ticket_id=ticket.id,
        company_id=1,
        status=st_val,
        start_time=now_time,
        moved_by_id=user_id,
    )
    db.add(t_history)
    db.commit()
    db.refresh(ticket)

    ticket_dict = format_ticket(ticket)
    safe_payload = jsonable_encoder(ticket_dict)

    log_action(db, user_id, user_role, "CREATED", "Ticket", ticket.id, safe_payload)

    # ─── CONDITION 1 TRIGGER: TICKET CREATION NOTIFICATION ───
    # try:
    #     # Fetch the Deal to identify the Deal Owner entity
    #     deal_record = db.query(Deal).filter(Deal.id == int(ticket.deal_id)).first()
    #     if deal_record and deal_record.deal_owner_id:
    #         from src.models.user import User

    #         deal_owner = (
    #             db.query(User).filter(User.id == int(deal_record.deal_owner_id)).first()
    #         )

    #         if deal_owner and deal_owner.email:
    #             recipient_emails = [deal_owner.email]

    #             # Dynamic Supervisor Registry Mapping Lookup Loop
    #             reporting_manager_id = None
    #             for mgr_id, executive_ids in MANAGERID.MANAGER_EXECUTIVES_MAP.items():
    #                 if deal_owner.id in executive_ids:
    #                     reporting_manager_id = mgr_id
    #                     break

    #             if reporting_manager_id:
    #                 manager_user = (
    #                     db.query(User)
    #                     .filter(User.id == int(reporting_manager_id))
    #                     .first()
    #                 )
    #                 if manager_user and manager_user.email:
    #                     recipient_emails.append(manager_user.email)

                # from src.controllers.Background_threads import BackgroundThreadPool
                # from src.controllers.mail import notify_ticket_created
                #
                # clean_targets = list(
                #     {email.strip() for email in recipient_emails if email}
                # )
                #
                # BackgroundThreadPool.execute_task(
                #     notify_ticket_created,
                #     clean_targets,
                #     deal_record.account_name or "Unknown Account",
                #     ticket.id,
                # )
    # except Exception as create_mail_err:
    #     print(f"Warning: Ticket creation notification loop bypassed: {create_mail_err}")

    return ticket_dict


@tickets_router.patch("/{ticket_id}")
@tickets_router.put("/{ticket_id}")
async def update_ticket(
    ticket_id: int, request: Request, db: Session = Depends(get_db)
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.archived_at is not None:
        raise HTTPException(
            status_code=400,
            detail="Cannot modify an archived ticket. Restore it first.",
        )
    if (ticket.deal and ticket.deal.archived_at is not None) or (
        ticket.account and ticket.account.archived_at is not None
    ):
        raise HTTPException(
            status_code=400,
            detail="Cannot modify ticket under an archived deal or account.",
        )

    # Capture the historical login state before the payload write loop modifies memory space
    old_ticket_login = ticket.ticket_login

    body = await request.json()

    body.pop("id", None)
    body.pop("deal_id", None)
    body.pop("created_at", None)
    body.pop("created_by", None)

    # --- Duplicate ticket check on UPDATE: same deal + lender_name (excluding self) ---
    new_lender_name = body.get("lender_name")
    if new_lender_name != "Not Applicable":
        if new_lender_name and new_lender_name != ticket.lender_name:
            duplicate_ticket = (
                db.query(Ticket)
                .filter(
                    Ticket.deal_id == ticket.deal_id,
                    Ticket.lender_name == new_lender_name,
                    Ticket.id != ticket_id,  # exclude self
                )
                .first()
            )
            if duplicate_ticket:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        'A similar ticket with same "Lender Name" already exist, '
                        'Please try changing the "Lender Name" else refer to the existing tickets'
                    ),
                )

    if "call_back_date_time" in body and "ticket_call_back_datetime" not in body:
        body["ticket_call_back_datetime"] = body["call_back_date_time"]

    old_ticket_status = ticket.ticket_status

    for key, value in body.items():
        if key == "ticket_call_back_datetime":
            if value == "" or value is None:
                setattr(ticket, key, None)
            else:
                if isinstance(value, str):
                    try:
                        clean_val = value.replace("Z", "+00:00")
                        parsed = datetime.fromisoformat(clean_val)
                        if parsed.tzinfo is None:
                            parsed = parsed.replace(tzinfo=timezone.utc)
                        if parsed < datetime.now(timezone.utc):
                            raise HTTPException(
                                status_code=400,
                                detail={"message": "Date should not be in the past"},
                            )
                        setattr(ticket, key, parsed)
                    except ValueError:
                        raise HTTPException(
                            status_code=400,
                            detail={"message": f"Invalid datetime format for {key}"},
                        )
                elif isinstance(value, datetime):
                    if value.tzinfo is None:
                        value = value.replace(tzinfo=timezone.utc)
                    if value < datetime.now(timezone.utc):
                        raise HTTPException(
                            status_code=400,
                            detail={"message": "Date should not be in the past"},
                        )
                    setattr(ticket, key, value)
                else:
                    setattr(ticket, key, value)
        elif hasattr(ticket, key):
            setattr(ticket, key, value)

    user_id = request.state.user_id
    user_role = request.state.role
    ticket.modified_by = user_id

    new_ticket_status = ticket.ticket_status
    if new_ticket_status and new_ticket_status != old_ticket_status:
        now_time = datetime.now(timezone.utc)
        active_rec = (
            db.query(TicketStatusHistory)
            .filter(
                TicketStatusHistory.ticket_id == ticket.id,
                TicketStatusHistory.end_time.is_(None),
            )
            .order_by(TicketStatusHistory.start_time.desc())
            .first()
        )
        if active_rec:
            active_rec.end_time = now_time
            start_dt = active_rec.start_time
            if start_dt and start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            dur_secs = (
                max(int((now_time - start_dt).total_seconds()), 0) if start_dt else 0
            )
            active_rec.duration_seconds = dur_secs
            active_rec.total_time_stayed = format_ticket_duration_short(dur_secs)
        else:
            last_rec = (
                db.query(TicketStatusHistory)
                .filter(TicketStatusHistory.ticket_id == ticket.id)
                .order_by(TicketStatusHistory.end_time.desc())
                .first()
            )
            start_dt = (
                last_rec.end_time
                if (last_rec and last_rec.end_time)
                else ticket.created_at
            ) or now_time
            if start_dt and start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            dur_secs = max(int((now_time - start_dt).total_seconds()), 0) if start_dt else 0
            prev_status = old_ticket_status or "Yet to Lender Login"
            prev_rec = TicketStatusHistory(
                ticket_id=ticket.id,
                company_id=1,
                status=prev_status,
                start_time=start_dt,
                end_time=now_time,
                duration_seconds=dur_secs,
                total_time_stayed=format_ticket_duration_short(dur_secs),
                moved_by_id=user_id,
            )
            db.add(prev_rec)

        new_history = TicketStatusHistory(
            ticket_id=ticket.id,
            company_id=1,
            status=new_ticket_status,
            start_time=now_time,
            moved_by_id=user_id,
        )
        db.add(new_history)

    db.commit()
    db.refresh(ticket)

    log_action(db, user_id, user_role, "UPDATED", "Ticket", ticket.id, body)

    # ─── CONDITIONS 2 & 3 TRIGGER: TICKET LOGIN FIELDS STATUS MODIFICATIONS ───
    new_ticket_login = body.get("ticket_login")

    # Fire workflow evaluation ONLY if ticket_login value is explicitly changing
    if (
        new_ticket_login is not None
        and str(new_ticket_login).strip() != str(old_ticket_login).strip()
    ):
        try:
            deal_record = db.query(Deal).filter(Deal.id == int(ticket.deal_id)).first()
            if deal_record and deal_record.deal_owner_id:
                from src.models.user import User

                deal_owner = (
                    db.query(User)
                    .filter(User.id == int(deal_record.deal_owner_id))
                    .first()
                )

                if deal_owner and deal_owner.email:
                    recipient_emails = [deal_owner.email]

                    # Supervisor Hierarchy Map Resolution Lookup Matrix
                    reporting_manager_id = None
                    for (
                        mgr_id,
                        executive_ids,
                    ) in MANAGERID.MANAGER_EXECUTIVES_MAP.items():
                        if deal_owner.id in executive_ids:
                            reporting_manager_id = mgr_id
                            break

                    if reporting_manager_id:
                        manager_user = (
                            db.query(User)
                            .filter(User.id == int(reporting_manager_id))
                            .first()
                        )
                        if manager_user and manager_user.email:
                            recipient_emails.append(manager_user.email)

                    clean_targets = list(
                        {email.strip() for email in recipient_emails if email}
                    )

                    # from src.controllers.Background_threads import BackgroundThreadPool
                    # from src.controllers.mail import (
                    #     notify_ticket_approved,
                    #     notify_ticket_disapproved,
                    # )
                    #
                    # # Evaluate Condition 2: Field is modified to Approved
                    # if str(new_ticket_login).strip().lower() == "approved":
                    #     BackgroundThreadPool.execute_task(
                    #         notify_ticket_approved,
                    #         clean_targets,
                    #         ticket.lender_name,
                    #         ticket.id,
                    #     )
                    #
                    # # Evaluate Condition 3: Field is modified to Disapproved
                    # elif str(new_ticket_login).strip().lower() == "disapproved":
                    #     BackgroundThreadPool.execute_task(
                    #         notify_ticket_disapproved,
                    #         clean_targets,
                    #         ticket.lender_name,
                    #         ticket.id,
                    #     )
        except Exception as update_mail_err:
            print(
                f"Warning: Ticket update transactional alert skipped: {update_mail_err}"
            )

    return format_ticket(ticket)


@tickets_router.get("/{ticket_id}")
def get_ticket(
    ticket_id: int,
    request: Request,
    db: Session = Depends(get_db),
    mongodb_conn=Depends(get_mongodb),
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    user_role = getattr(request.state, "role", None)
    from src.utility.archive_visibility import is_super_admin
    is_archived = (
        ticket.archived_at is not None
        or (ticket.deal and ticket.deal.archived_at is not None)
        or (ticket.account and ticket.account.archived_at is not None)
    )
    if is_archived and not is_super_admin(user_role):
        raise HTTPException(status_code=404, detail="Ticket not found")

    result = format_ticket(ticket)
    j_list = build_batch_ticket_status_journeys(db, [ticket_id]).get(ticket_id, [])
    result["status_journey"] = j_list
    result["journey"] = j_list
    result["notes"] = get_notes(
        id_list=[str(ticket_id)],
        notes_collection=mongodb_conn["Notes"],
        module_name="Tickets",
    )
    return result


@tickets_router.delete("/{ticket_id}")
def delete_ticket(ticket_id: int, request: Request, db: Session = Depends(get_db)):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.archived_at is not None:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete an archived ticket. Restore it first.",
        )
    if (ticket.deal and ticket.deal.archived_at is not None) or (
        ticket.account and ticket.account.archived_at is not None
    ):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete ticket under an archived deal or account.",
        )

    db.delete(ticket)
    db.commit()
    return {"message": "Ticket deleted"}


@tickets_router.post("/tickets-update-csv-upload")
async def tickets_update_csv(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user_role = request.state.role
    if user_role not in ("super_admin", "admin", "manager"):
        raise HTTPException(
            status_code=403, detail="You do not have permission to upload CSV"
        )
    try:
        user_id = int(request.state.user_id)
        return await update_tickets_based_on_csv(file, db, user_id, user_role)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"unable to process csv error: {str(e)}"
        )


async def update_tickets_based_on_csv(file: UploadFile, db: Session, user_id: int, user_role: str):
    import csv
    import io
    from starlette.responses import JSONResponse
    from decimal import Decimal
    from datetime import date
    from sqlalchemy.exc import SQLAlchemyError
    from src.utility.utils import get_ticket_headers

    insertion_tickets, updation_tickets, error_list = [], [], []
    row_number = 1

    allowed_owner_ids = None
    if user_role == "manager":
        allowed_owner_ids = {int(user_id)} | set(
            MANAGERID.MANAGER_EXECUTIVES_MAP.get(int(user_id), [])
        )

    # Date fields that must be YYYY-MM-DD
    DATE_FIELDS = {
        "lender_login_date",
        "targeted_disbursement_date",
        "disbursement_date",
        "loan_start_date",
        "loan_end_date"
    }

    # Integer fields
    INT_FIELDS = {
        "id",
        "deal_id",
        "account_id",
        "tenure"
    }

    # Numeric (Decimal) fields
    DECIMAL_FIELDS = {
        "potential",
        "approved_amount",
        "sanction_amount",
        "processing_fees",
        "disbursed_amount",
        "pf_percentage",
        "insurance_amount",
        "rate_of_interest"
    }

    try:
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV files are supported")

        contents = await file.read()
        decoded = contents.decode("utf-8-sig", errors="replace").splitlines()
        reader = csv.DictReader(decoded)
        data = list(reader)

        if not data:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        ticket_headers = get_ticket_headers()
        csv_headers = {col.strip().lower() for col in (reader.fieldnames or [])}
        missing_headers = ticket_headers - csv_headers
        if missing_headers:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Header mismatch found",
                    "missing_headers": sorted(missing_headers),
                },
            )

        # Track local ticket counts per deal to generate sequence names correctly
        deal_ticket_counts = {}

        for row in data:
            row_number += 1
            try:
                row = {
                    k.strip().lower(): (v.strip() if v and v.strip() else None)
                    for k, v in row.items()
                }

                is_new = not row.get("id")

                # Parse Integer fields
                for field in INT_FIELDS:
                    if row.get(field):
                        try:
                            row[field] = int(row[field])
                        except ValueError:
                            raise ValueError(f"Invalid integer value for {field}: '{row[field]}'")

                # Parse Decimal fields
                for field in DECIMAL_FIELDS:
                    if row.get(field):
                        try:
                            row[field] = Decimal(row[field])
                        except Exception:
                            raise ValueError(f"Invalid numeric value for {field}: '{row[field]}'")

                # Parse Date fields (YYYY-MM-DD)
                for field in DATE_FIELDS:
                    if row.get(field):
                        try:
                            row[field] = date.fromisoformat(row[field][:10])
                        except ValueError:
                            raise ValueError(f"Invalid date for {field}: '{row[field]}'; expected YYYY-MM-DD")

                if is_new:
                    deal_id_val = row.get("deal_id")
                    if not deal_id_val:
                        raise ValueError("deal_id is required for new tickets")

                    parent_deal = db.query(Deal).filter(Deal.id == int(deal_id_val)).first()
                    if not parent_deal:
                        raise ValueError(f"Parent deal with ID {deal_id_val} not found")

                    if user_role == "manager":
                        if parent_deal.deal_owner_id is not None and int(parent_deal.deal_owner_id) not in allowed_owner_ids:
                            raise HTTPException(
                                status_code=403,
                                detail=f"Row {row_number}: You do not have permission to add a ticket to deal owned by user ID {parent_deal.deal_owner_id}"
                            )

                    # Auto-generate ticket name
                    if deal_id_val not in deal_ticket_counts:
                        existing_count = db.query(Ticket).filter(Ticket.deal_id == int(deal_id_val)).count()
                        deal_ticket_counts[deal_id_val] = existing_count

                    deal_ticket_counts[deal_id_val] += 1
                    ticket_sequence = deal_ticket_counts[deal_id_val]
                    parent_deal_name = parent_deal.deal_name or parent_deal.account_name or str(deal_id_val)
                    generated_ticket_name = f"{parent_deal_name}/T{ticket_sequence:02d}"

                    row["ticket_name"] = generated_ticket_name
                    row["account_id"] = parent_deal.account_id
                    row.pop("id", None)
                    row["created_by"] = int(user_id)
                    row["modified_by"] = int(user_id)
                    insertion_tickets.append(row)

                else:
                    existing_ticket = db.query(Ticket).filter(Ticket.id == row["id"]).first()
                    if not existing_ticket:
                        raise ValueError(f"Ticket with ID {row['id']} not found")

                    parent_deal = db.query(Deal).filter(Deal.id == existing_ticket.deal_id).first()
                    if not parent_deal:
                        raise ValueError(f"Parent deal for ticket ID {row['id']} not found")

                    if user_role == "manager":
                        if parent_deal.deal_owner_id is not None and int(parent_deal.deal_owner_id) not in allowed_owner_ids:
                            raise HTTPException(
                                status_code=403,
                                detail=f"Row {row_number}: You do not have permission to update ticket owned by user ID {parent_deal.deal_owner_id}"
                            )

                    row.pop("deal_id", None)  # Prevent changing deal_id on update
                    row["account_id"] = parent_deal.account_id
                    row["modified_by"] = int(user_id)
                    updation_tickets.append(row)

            except HTTPException:
                raise
            except Exception as row_err:
                error_list.append({"row": row_number, "error": str(row_err)})

        if not insertion_tickets and not updation_tickets:
            return JSONResponse(
                status_code=200,
                content=jsonable_encoder({
                    "total_inserted": 0,
                    "total_updated": 0,
                    "row_errors": error_list,
                }),
            )

        db_result = update_and_insert_tickets(
            insertion_tickets, updation_tickets, db, user_id, user_role
        )
        return JSONResponse(
            status_code=200,
            content=jsonable_encoder({
                "total_inserted": db_result["inserted"],
                "total_updated": db_result["updated"],
                "row_errors": error_list + db_result["failed"],
            }),
        )

    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content=jsonable_encoder({"detail": f"Processing error: {str(e)}", "row_errors": error_list}),
        )


def update_and_insert_tickets(insertion_tickets, updation_tickets, db: Session, user_id: int, user_role: str):
    from sqlalchemy.exc import SQLAlchemyError
    inserted = 0
    updated = 0
    failed = []

    for tick in insertion_tickets:
        try:
            # Duplicate check
            deal_id_val = tick.get("deal_id")
            new_lender_name = tick.get("lender_name")
            if new_lender_name:
                duplicate_ticket = (
                    db.query(Ticket)
                    .filter(
                        Ticket.deal_id == int(deal_id_val),
                        Ticket.lender_name == new_lender_name,
                    )
                    .first()
                )
                if duplicate_ticket:
                    raise ValueError(f"Duplicate ticket with lender name '{new_lender_name}' already exists for this deal")

            ticket = Ticket(**tick)
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            inserted += 1
            log_action(db, user_id, user_role, "CREATED", "Ticket", ticket.id, jsonable_encoder(format_ticket(ticket)))
        except SQLAlchemyError as e:
            db.rollback()
            failed.append({"type": "insert", "data": tick, "error": str(e)})
        except ValueError as e:
            db.rollback()
            failed.append({"type": "insert", "data": tick, "error": str(e)})

    for tick in updation_tickets:
        try:
            ticket = db.query(Ticket).filter(Ticket.id == tick["id"]).first()
            if not ticket:
                raise ValueError("Ticket ID not found")

            # Duplicate check
            new_lender_name = tick.get("lender_name")
            if new_lender_name and new_lender_name != ticket.lender_name:
                duplicate_ticket = (
                    db.query(Ticket)
                    .filter(
                        Ticket.deal_id == ticket.deal_id,
                        Ticket.lender_name == new_lender_name,
                        Ticket.id != ticket.id,
                    )
                    .first()
                )
                if duplicate_ticket:
                    raise ValueError(f"Duplicate ticket with lender name '{new_lender_name}' already exists for this deal")

            for key, value in tick.items():
                if key == "id":
                    continue
                setattr(ticket, key, value)

            db.commit()
            db.refresh(ticket)
            updated += 1
            log_action(db, user_id, user_role, "UPDATED", "Ticket", ticket.id, tick)
        except SQLAlchemyError as e:
            db.rollback()
            failed.append({"type": "update", "data": tick, "error": str(e)})
        except ValueError as e:
            db.rollback()
            failed.append({"type": "update", "data": tick, "error": str(e)})

    return {"inserted": inserted, "updated": updated, "failed": failed}
