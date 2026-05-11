import math
from datetime import datetime, timedelta, timezone, date

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_
from sqlalchemy.orm import Session, selectinload

from src.controllers.audit_log import log_action
from src.controllers.auth import MANAGERID
from src.controllers.notes import get_notes
from src.models.deal import Deal
from src.models.ticket import Ticket


def get_deals(
    page,
    db: Session,
    mongodb_conn,
    user_id: int,
    user_role: str,
    deal_id: int | None = None,
    account_name: str | None = None,
    deal_status: str | None = None,
    loan_type: str | None = None,
    deal_owner_id: int | None = None,
    lender_name: str | None = None,
    lender_login_type: str | None = None,
    ticket_login: str | None = None,
    type_of_case_login: str | None = None,
    kanban: bool = False,
    expected_closing_from: str | None = None,
    expected_closing_to: str | None = None,
    status_closing_from: str | None = None,
    status_closing_to: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
):
    try:
        from src.models.ticket import (
            Ticket,  # Explicit import to prevent relationship lookup failure
        )

        MANAGER_EXECUTIVES_MAP = MANAGERID.MANAGER_EXECUTIVES_MAP
        page = page or 1
        limit = 30
        offset = (page - 1) * limit
        filters = []
        allowed_owner_ids = None

        if user_role == "manager":
            allowed_owner_ids = [user_id] + MANAGER_EXECUTIVES_MAP.get(user_id, [])
        elif user_role == "executive":
            allowed_owner_ids = [user_id]

        if allowed_owner_ids is not None:
            filters.append(Deal.deal_owner_id.in_(allowed_owner_ids))

        if deal_id:
            filters.append(Deal.id == deal_id)
        if account_name:
            filters.append(Deal.account_name.ilike(f"%{account_name.strip()}%"))
        if deal_status:
            filters.append(Deal.deal_status.ilike(f"%{deal_status.strip()}%"))
        if loan_type:
            filters.append(Deal.loan_type.ilike(f"%{loan_type.strip()}%"))
        if deal_owner_id:
            filters.append(Deal.deal_owner_id == deal_owner_id)
        if lender_name:
            filters.append(Deal.lender_name.ilike(f"%{lender_name.strip()}%"))
        if lender_login_type:
            filters.append(Deal.lender_login_type.ilike(f"%{lender_login_type.strip()}%"))
        if ticket_login:
            filters.append(Deal.ticket_login.ilike(f"%{ticket_login.strip()}%"))
        if type_of_case_login:
            filters.append(Deal.type_of_case_login.ilike(f"%{type_of_case_login.strip()}%"))
            # Filter for Expected Closing Date Range
        if expected_closing_from:
            filters.append(Deal.deal_expected_closing >= expected_closing_from)
        if expected_closing_to:
            filters.append(Deal.deal_expected_closing <= expected_closing_to)

        # Filter for Status Closing Date Range
        if status_closing_from:
            filters.append(Deal.deal_status_closing >= status_closing_from)
        if status_closing_to:
            filters.append(Deal.deal_status_closing <= status_closing_to)

        if kanban:
            date_from = (
                datetime.strptime(created_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if created_from
                else datetime.now(timezone.utc) - timedelta(days=30)
            )
            date_to = (
                datetime.strptime(created_to, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                + timedelta(days=1)
                - timedelta(seconds=1)
                if created_to
                else datetime.now(timezone.utc)
            )
            filters.append(Deal.created_at >= date_from)
            filters.append(Deal.created_at <= date_to)

            base_query = db.query(Deal).filter(and_(*filters))
            deals = base_query.with_entities(
                Deal.id,
                Deal.account_name,
                Deal.lender_name,
                Deal.deal_status,
                Deal.loan_type,
                Deal.deal_owner_id,
                Deal.deal_expected_closing,
                Deal.deal_status_closing,
                Deal.lender_login_type,
                Deal.deal_status_closing,
                Deal.partner_code,
            ).all()
            grouped: dict = {}
            for deal in deals:
                status = deal.deal_status or "No Status"
                grouped.setdefault(status, []).append(
                    {
                        **deal._asdict(),
                        "id": str(deal.id),
                        "deal_owner_id": str(deal.deal_owner_id)
                        if deal.deal_owner_id
                        else None,
                    }
                )

            return {"data": grouped, "page_info": None}

        base_query = db.query(Deal).filter(and_(*filters))

        if deal_id:
            deals = base_query.options(selectinload(Deal.owner),selectinload(Deal.revenue)).limit(1).all()
            if deals:
                deal = deals[0]
                print("Revenue loaded:", deal.revenue)  # [] means no records
                print("Revenue type:", type(deal.revenue))

                ids_list = [str(deal.id)]
                if getattr(deal, "crm_deal_id", None):
                    ids_list.append(str(deal.crm_deal_id))

                # explicitly query tickets based on Deal ID to bypass relationship mapping issues
                tickets_records = db.query(Ticket).filter(Ticket.deal_id == deal.id).all()

                serialized_tickets = []
                for ticket in tickets_records:
                    ids_list.append(str(ticket.id))
                    t_dict = {
                        c.name: getattr(ticket, c.name) for c in ticket.__table__.columns
                    }

                    # Stringify IDs to match schema
                    for key in (
                        "id",
                        "deal_id",
                        "created_by",
                        "modified_by",
                        "partner_code",
                    ):
                        if t_dict.get(key) is not None:
                            t_dict[key] = str(t_dict[key])
                    serialized_tickets.append(t_dict)

                serialized_revenue = []
                if getattr(deal, "revenue", None):
                    for revenue in deal.revenue:
                        revenue_dict = {
                            c.name: getattr(revenue, c.name)
                            for c in revenue.__table__.columns
                        }
                        # Stringify IDs
                        for key in ("id", "deal_id", "owner_id", "created_by", "updated_by"):
                            if revenue_dict.get(key) is not None:
                                revenue_dict[key] = str(revenue_dict[key])

                        # Stringify dates/datetimes ← ADD THIS
                        for key, val in revenue_dict.items():
                            if isinstance(val, (date, datetime)):
                                revenue_dict[key] = val.isoformat()
                            if isinstance(val,float):
                                revenue_dict[key] = str(val)

                        serialized_revenue.append(revenue_dict)
                print("This is the serialized revenue list:", serialized_revenue)

                # fetch notes matching either Deal or Tickets modules
                notes = get_notes(
                    id_list=ids_list,
                    notes_collection=mongodb_conn["Notes"],
                    module_name=["Deals", "Tickets"],
                )

                # Manually construct the final Deal dictionary to ensure injection works
                deal_dict = {c.name: getattr(deal, c.name) for c in deal.__table__.columns}
                deal_dict["id"] = str(deal.id)
                # deal_dict["deal_status"] = getattr(deal, "deal_status", None)
                # deal_dict["deal_stage"] = getattr(deal, "deal_stage", None)
                if deal.deal_owner_id:
                    deal_dict["deal_owner_id"] = str(deal.deal_owner_id)
                if deal.account_id:
                    deal_dict["account_id"] = str(deal.account_id)

                deal_dict["payment_receipt"] = None
                deal_dict["notes"] = notes
                deal_dict["tickets"] = serialized_tickets
                deal_dict["revenue"] = serialized_revenue

                if getattr(deal, "owner", None):
                    deal_dict["owner"] = {
                        "id": str(deal.owner.id),
                        "full_name": getattr(deal.owner, "full_name", ""),
                        "email": getattr(deal.owner, "email", ""),
                    }

                return {
                    "data": [deal_dict],
                    "page_info": {"page": 1, "total_pages": 1, "data_size": 1},
                }

            return {
                "data": [],
                "page_info": {"page": 1, "total_pages": 0, "data_size": 0},
            }

        total_records = base_query.count()
        deals = (
            base_query.with_entities(
                Deal.id,
                Deal.account_name,
                Deal.lender_name,
                Deal.deal_status,
                Deal.deal_stage,
                Deal.loan_type,
                Deal.ticket_login,
                Deal.deal_owner_id,
                Deal.lender_login_type,
                Deal.partner_code,
                Deal.deal_expected_closing,
                Deal.deal_status_closing,
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
        total_pages = math.ceil(total_records / limit)

        return {
            "data": [
                {
                    **d._asdict(),
                    "id": str(d.id),
                    "deal_owner_id": str(d.deal_owner_id) if d.deal_owner_id else None,
                }
                for d in deals
            ],
            "page_info": {
                "page": page,
                "total_pages": total_pages,
                "data_size": total_records,
            },
        }
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Internal Server Error")

def create_deal(deal, db: Session, user_id, user_role):
    try:
        created_deal = Deal(
            account_id=deal.account_id,
            account_name=deal.account_name,
            deal_type=deal.deal_type,
            loan_type=deal.loan_type,
            type_of_login=deal.type_of_login,
            type_of_case_login=deal.type_of_case_login,
            ticket_login=deal.ticket_login,
            deal_stage=deal.deal_stage,
            deal_status=deal.deal_status,
            amount_required=deal.amount_required,
            mm_charges=deal.mm_charges,
            lender_name=deal.lender_name,
            lender_login_type=deal.lender_login_type,
            lender_code=deal.lender_code,
            deal_call_back_datetime=deal.deal_call_back_datetime,
            customer_rejection_reason=deal.customer_rejection_reason,
            customer_rejection_status_explanation=deal.customer_rejection_status_explanation,
            deal_owner_id=user_id,
            created_by=user_id,
            modified_by=user_id,
            deal_expected_closing=deal.deal_expected_closing,
            deal_status_closing=deal.deal_status_closing,
            partner_code=deal.partner_code,
        )
        db.add(created_deal)
        db.commit()
        db.refresh(created_deal)

        log_action(
            db, user_id, user_role, "CREATED", "Deal", created_deal.id,created_deal)

        return created_deal
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail={"message": str(e)})


def update_deal_based_on_id(user_id, user_role, db: Session, deal_id: int, payload):
    db_deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not db_deal:
        raise HTTPException(status_code=404, detail={"msg": "Deal not found"})

    for key, value in payload.items():
        if hasattr(db_deal, key):
            if value == "" or value is None:
                setattr(db_deal, key, None)
            elif "datetime" in key or "date" in key or "closing" in key:
                if isinstance(value, str):
                    try:
                        parsed = datetime.fromisoformat(value)
                        setattr(db_deal, key, parsed)
                    except ValueError:
                        raise HTTPException(
                            status_code=400,
                            detail={"msg": f"Invalid date format for field: {key}"},
                        )
                else:
                    setattr(db_deal, key, value)
            else:
                setattr(db_deal, key, value)

    db_deal.modified_by = user_id
    db_deal.updated_at = datetime.now(timezone.utc)

    try:
        db.commit()
        db.refresh(db_deal)
        log_action(db, user_id, user_role, "UPDATED", "Deal", deal_id, payload)
        return {"message": "update-success", "updated_deal_id": str(db_deal.id)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")


def get_deal_id(user_id: int, role: str, deal_name: str, db: Session):
    try:
        MANAGER_EXECUTIVES_MAP = MANAGERID.MANAGER_EXECUTIVES_MAP
        allowed_owner_ids = None
        filters = []  # this holds all the filters that are being applied by the users

        # ---------------- ROLE BASED ACCESS ---------------- #

        if role in ("super_admin", "admin"):
            pass

        elif role == "manager":
            allowed_owner_ids = [user_id] + MANAGER_EXECUTIVES_MAP.get(user_id, [])

        elif role == "executive":
            allowed_owner_ids = [user_id]

        if allowed_owner_ids is not None:
            filters.append(Deal.deal_owner_id.in_(allowed_owner_ids))
         #append the query-parameter
        filters.append(Deal.account_name.ilike(f"{deal_name.strip()}%"))

        data = db.query(Deal.id,Deal.account_name).filter(*filters)

        serialized_deals = []

        for deal in data:
            revenue_dict = {
                "id": str(deal.id),
                "account_name": deal.account_name
            }
            serialized_deals.append(revenue_dict)


        return {
            "success": True,
            "message":"Deal lookup fetched successfully",
            "data":serialized_deals
        }
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Internal server error")

