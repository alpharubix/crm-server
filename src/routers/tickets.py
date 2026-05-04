from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_
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
    for key in ("id", "deal_id", "created_by", "modified_by", "partner_code"):
        if data.get(key) is not None:
            data[key] = str(data[key])
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
    ticket_status: str | None = None,
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
        filters.append(Ticket.ticket_status.ilike(f"%{ticket_status.strip()}%"))
    if type_of_loan:
        filters.append(Ticket.type_of_loan.ilike(f"%{type_of_loan.strip()}%"))

    if kanban:
        date_from = (
            datetime.strptime(created_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if created_from
            else datetime.now(timezone.utc) - timedelta(days=30)
        )
        date_to = (
            datetime.strptime(created_to, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if created_to
            else datetime.now(timezone.utc)
        )
        if lender_login_from:
            try:
                # Assuming format YYYY-MM-DD
                low_date = datetime.strptime(lender_login_from, "%Y-%m-%d").date()
                filters.append(Ticket.lender_login_date >= low_date)
            except ValueError:
                pass  # Or handle error for invalid date format

        if lender_login_to:
            try:
                high_date = datetime.strptime(lender_login_to, "%Y-%m-%d").date()
                filters.append(Ticket.lender_login_date <= high_date)
            except ValueError:
                pass

        if targeted_disbursement_from:
            try:
                low_date = datetime.strptime(
                    targeted_disbursement_from, "%Y-%m-%d"
                ).date()
                filters.append(Ticket.targeted_disbursement_date >= low_date)
            except ValueError:
                pass

        if targeted_disbursement_to:
            try:
                high_date = datetime.strptime(
                    targeted_disbursement_to, "%Y-%m-%d"
                ).date()
                filters.append(Ticket.targeted_disbursement_date <= high_date)
            except ValueError:
                pass
        if disbursement_from:
            try:
                low_date = datetime.strptime(disbursement_from, "%Y-%m-%d").date()
                filters.append(Ticket.disbursement_date >= low_date)
            except ValueError:
                pass

        if disbursement_to:
            try:
                high_date = datetime.strptime(disbursement_to, "%Y-%m-%d").date()
                filters.append(Ticket.disbursement_date <= high_date)
            except ValueError:
                pass

        if deal_owner_id:
            filters.append(Deal.deal_owner_id == deal_owner_id)

        filters.append(Ticket.created_at >= date_from)
        filters.append(Ticket.created_at <= date_to)

        query = (
            db.query(Ticket)
            .join(Deal, Ticket.deal_id == Deal.id)
            .filter(and_(*filters))
        )
        total_count = query.count()

        tickets = query.options(selectinload(Ticket.deal)).all()

        if allowed_owner_ids is not None:
            query = query.filter(Deal.deal_owner_id.in_(allowed_owner_ids))
        if account_name:
            query = query.filter(Deal.account_name.ilike(f"%{account_name.strip()}%"))

        tickets = query.options(selectinload(Ticket.deal)).all()

        grouped_data = {}
        for t in tickets:
            status = t.ticket_status or "No Status"
            ticket_dict = format_ticket(t)
            ticket_dict["account_name"] = t.deal.account_name if t.deal else "-"
            ticket_dict["deal_owner_id"] = (
                str(t.deal.deal_owner_id) if t.deal and t.deal.deal_owner_id else None
            )
            grouped_data.setdefault(status, []).append(ticket_dict)

        return {"data": grouped_data, "page_info": {"total": total_count}}

    # Standard list view
    limit = 100
    offset = (page - 1) * limit

    query = (
        db.query(Ticket).join(Deal, Ticket.deal_id == Deal.id).filter(and_(*filters))
    )

    if allowed_owner_ids is not None:
        query = query.filter(Deal.deal_owner_id.in_(allowed_owner_ids))
    if account_name:
        query = query.filter(Deal.account_name.ilike(f"%{account_name.strip()}%"))

    total = query.count()
    tickets = query.order_by(Ticket.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "data": [format_ticket(t) for t in tickets],
        "page_info": {"page": page, "total": total},
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
    }

    filtered_body = {k: v for k, v in body.items() if k in allowed_fields}

    user_id = request.state.user_id
    user_role = request.state.role

    ticket = Ticket(**filtered_body, created_by=user_id)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    ticket_dict = format_ticket(ticket)
    safe_payload = jsonable_encoder(ticket_dict)

    log_action(db, user_id, user_role, "CREATED", "Ticket", ticket.id, safe_payload)

    return ticket_dict


@tickets_router.patch("/{ticket_id}")
@tickets_router.put("/{ticket_id}")
async def update_ticket(
    ticket_id: int, request: Request, db: Session = Depends(get_db)
):
    ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()

    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    body = await request.json()

    body.pop("id", None)
    body.pop("deal_id", None)
    body.pop("created_at", None)
    body.pop("created_by", None)

    for key, value in body.items():
        if hasattr(ticket, key):
            setattr(ticket, key, value)

    user_id = request.state.user_id
    user_role = request.state.role
    ticket.modified_by = user_id

    db.commit()
    db.refresh(ticket)

    log_action(db, user_id, user_role, "UPDATED", "Ticket", ticket.id, body)

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
