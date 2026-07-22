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
    if int(user_id) in MANAGERID.BYPASS_USER_IDS:
        pass
    elif user_role == "manager":
        allowed_owner_ids = [user_id] + MANAGER_EXECUTIVES_MAP.get(user_id, [])
    elif user_role == "executive":
        allowed_owner_ids = [user_id]

    filters = []

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

    return {
        "data": [format_ticket(t) for t in tickets],
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
    ticket_sequence = existing_ticket_count + 1000
    parent_deal_name = parent_deal.deal_name or parent_deal.account_name or str(deal_id_val)
    generated_ticket_name = f"{parent_deal_name}/TK{ticket_sequence}"
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
