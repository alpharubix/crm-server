import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, selectinload

from src.controllers.audit_log import log_action
from src.controllers.auth import MANAGERID
from src.controllers.notes import get_notes
from src.database import get_db, get_mongodb

# Ensure Deal is imported
from src.models.deal import Deal
from src.models.ticket import Ticket

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
        "partner_code",
    ):
        if data.get(key) is not None:
            data[key] = str(data[key])

    # Ensure account_name is always included in the returned ticket dict
    data["account_name"] = (
        t.account.account_name
        if t.account
        else (t.deal.account_name if t.deal else "-")
    )
    data["deal_owner_id"] = (
        str(t.deal.deal_owner_id) if t.deal and t.deal.deal_owner_id else None
    )
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
    if user_role == "manager":
        allowed_owner_ids = [user_id] + MANAGER_EXECUTIVES_MAP.get(user_id, [])
    elif user_role == "executive":
        allowed_owner_ids = [user_id]

    filters = []

    if deal_id:
        filters.append(Ticket.deal_id == deal_id)
    if ticket_status:
        statuses = [
            s.strip()
            for s in (
                ticket_status if isinstance(ticket_status, list) else [ticket_status]
            )
            if s and s.strip()
        ]
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
        filters.append(Deal.deal_owner_id.in_(allowed_owner_ids))
    if deal_owner_id:
        filters.append(Deal.deal_owner_id == deal_owner_id)
    if account_name:
        filters.append(Deal.account_name.ilike(f"%{account_name.strip()}%"))

    # Build the final unified query structure
    final_query = (
        db.query(Ticket).join(Deal, Ticket.deal_id == Deal.id).filter(and_(*filters))
    )

    if kanban:
        total_count = final_query.count()

        tickets = (
            final_query.options(selectinload(Ticket.deal), selectinload(Ticket.account))
            .limit(200)
            .all()
        )

        grouped_data = {}
        for t in tickets:
            status = t.ticket_status or "No Status"
            ticket_dict = format_ticket(t)
            grouped_data.setdefault(status, []).append(ticket_dict)

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

    return {
        "data": [format_ticket(t) for t in tickets],
        "page_info": {
            "page": page,
            "total_pages": total_pages,
            "data_size": total,
            "has_more": page < total_pages,
        },
    }


@tickets_router.post("")
@tickets_router.post("/")
async def create_ticket(request: Request, db: Session = Depends(get_db)):
    body = await request.json()

    if "deal_id" not in body:
        raise HTTPException(status_code=400, detail="deal_id is required")

    allowed_fields = {
        "deal_id",
        "loan_account_status",
        "ticket_login",
        "lender_name",
        "potential",
        "lender_login_type",
        "lender_login_date",
        "partner_code",
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
    }

    filtered_body = {k: v for k, v in body.items() if k in allowed_fields}

    user_id = request.state.user_id
    user_role = request.state.role

    # --- Auto-generate ticket_name: {deal_name}/T{seq} ---
    deal_id_val = body.get("deal_id")
    parent_deal = db.query(Deal).filter(Deal.id == int(deal_id_val)).first()
    if not parent_deal:
        raise HTTPException(status_code=404, detail="Parent deal not found")

    existing_ticket_count = (
        db.query(Ticket).filter(Ticket.deal_id == int(deal_id_val)).count()
    )
    ticket_sequence = existing_ticket_count + 1
    parent_deal_name = (
        parent_deal.deal_name or parent_deal.account_name or str(deal_id_val)
    )
    generated_ticket_name = f"{parent_deal_name}/T{ticket_sequence:02d}"
    filtered_body["ticket_name"] = generated_ticket_name

    # --- Duplicate ticket check: same deal + lender_name ---
    new_lender_name = body.get("lender_name")
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
            raise HTTPException(
                status_code=409,
                detail=(
                    'A similar ticket with same "Lender Name" already exist, '
                    'Please try changing the "Lender Name" else refer to the existing tickets'
                ),
            )

    ticket = Ticket(**filtered_body, created_by=user_id)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    ticket_dict = format_ticket(ticket)
    safe_payload = jsonable_encoder(ticket_dict)

    log_action(db, user_id, user_role, "CREATED", "Ticket", ticket.id, safe_payload)
    db.commit()  # ✅ commit audit log (log_action no longer self-commits)

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

    # Capture the historical login state before the payload write loop modifies memory space
    old_ticket_login = ticket.ticket_login

    body = await request.json()

    body.pop("id", None)
    body.pop("deal_id", None)
    body.pop("created_at", None)
    body.pop("created_by", None)

    # --- Duplicate ticket check on UPDATE: same deal + lender_name (excluding self) ---
    new_lender_name = body.get("lender_name")
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

    for key, value in body.items():
        if hasattr(ticket, key):
            setattr(ticket, key, value)

    user_id = request.state.user_id
    user_role = request.state.role
    ticket.modified_by = user_id

    db.commit()
    db.refresh(ticket)

    log_action(db, user_id, user_role, "UPDATED", "Ticket", ticket.id, body)
    db.commit()  # ✅ commit audit log (log_action no longer self-commits)

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

    result = format_ticket(ticket)
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

    db.delete(ticket)
    db.commit()
    return {"message": "Ticket deleted"}
