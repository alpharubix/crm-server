import math
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException,UploadFile
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, selectinload

from src.controllers.audit_log import log_action
from src.controllers.auth import MANAGERID
from src.controllers.notes import get_notes
from src.models.deal import Deal


def get_deals(
    page,
    db: Session,
    mongodb_conn,
    user_id: int,
    user_role: str,
    deal_id: int | None = None,
    account_name: str | None = None,
    deal_status: list[str] | None = None,
    loan_type: list[str] | None = None,
    deal_owner_id: list[int] | None = None,
    lender_name: list[str] | None = None,
    lender_login_type: str | None = None,
    ticket_login: list[str] | None = None,
    type_of_case_login: list[str] | None = None,
    kanban: bool = False,
    expected_closing_from: str | None = None,
    expected_closing_to: str | None = None,
    status_closing_from: str | None = None,
    status_closing_to: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
):
    try:
        from src.models.ticket import Ticket  # Prevent relationship lookup loop

        MANAGER_EXECUTIVES_MAP = MANAGERID.MANAGER_EXECUTIVES_MAP
        page = page or 1
        limit = 30
        offset = (page - 1) * limit
        filters = [or_(Deal.company_id == 1, Deal.company_id.is_(None))]

        # 1. Role-Based Access Scoping
        allowed_owner_ids = None
        if user_id in MANAGERID.BYPASS_USER_IDS:
            pass
        elif user_role == "manager":
            allowed_owner_ids = [user_id] + MANAGER_EXECUTIVES_MAP.get(user_id, [])
        elif user_role == "executive":
            allowed_owner_ids = [user_id]

        if allowed_owner_ids is not None:
            filters.append(Deal.deal_owner_id.in_(allowed_owner_ids))

        # 2. String Match Query Filters
        if deal_id:
            filters.append(Deal.id == deal_id)
        if account_name:
            filters.append(Deal.account_name.ilike(f"%{account_name.strip()}%"))
        if deal_status:
            statuses = [s.strip() for s in (deal_status if isinstance(deal_status, list) else [deal_status]) if s and s.strip()]
            if statuses:
                filters.append(
                    or_(*[Deal.deal_status.ilike(f"%{s}%") for s in statuses])
                )
        if loan_type:
            loan_types = loan_type if isinstance(loan_type, list) else [loan_type]
            filters.append(
                or_(*[Deal.loan_type.ilike(lt.strip()) for lt in loan_types])
            )
        if deal_owner_id:
            filters.append(Deal.deal_owner_id.in_(deal_owner_id))
        if lender_name:
            lenders = [l.strip() for l in (lender_name if isinstance(lender_name, list) else [lender_name]) if l and l.strip()]
            if lenders:
                filters.append(
                    or_(*[Deal.lender_name.ilike(f"%{l}%") for l in lenders])
                )
        if lender_login_type:
            filters.append(
                Deal.lender_login_type.ilike(f"%{lender_login_type.strip()}%")
            )
        if ticket_login:
            tickets = [t.strip() for t in (ticket_login if isinstance(ticket_login, list) else [ticket_login]) if t and t.strip()]
            if tickets:
                filters.append(
                    or_(*[Deal.ticket_login.ilike(f"%{t}%") for t in tickets])
                )
        if type_of_case_login:
            cases = [c.strip() for c in (type_of_case_login if isinstance(type_of_case_login, list) else [type_of_case_login]) if c and c.strip()]
            if cases:
                filters.append(
                    or_(*[Deal.type_of_case_login.ilike(f"%{c}%") for c in cases])
                )

        # 3. Handle Safe Date Parameter Conversions
        if expected_closing_from:
            try:
                filters.append(
                    Deal.deal_expected_closing
                    >= datetime.strptime(expected_closing_from, "%Y-%m-%d").date()
                )
            except ValueError:
                pass
        if expected_closing_to:
            try:
                filters.append(
                    Deal.deal_expected_closing
                    <= datetime.strptime(expected_closing_to, "%Y-%m-%d").date()
                )
            except ValueError:
                pass

        if status_closing_from:
            try:
                filters.append(
                    Deal.deal_status_closing
                    >= datetime.strptime(status_closing_from, "%Y-%m-%d").date()
                )
            except ValueError:
                pass
        if status_closing_to:
            try:
                filters.append(
                    Deal.deal_status_closing
                    <= datetime.strptime(status_closing_to, "%Y-%m-%d").date()
                )
            except ValueError:
                pass

        # 4. Handle Record Creation Timestamps (Accessible by both Kanban & Standard List Views)
        if created_from:
            try:
                date_from = datetime.strptime(created_from, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                filters.append(Deal.created_at >= date_from)
            except ValueError:
                pass
        if created_to:
            try:
                date_to = (
                    datetime.strptime(created_to, "%Y-%m-%d").replace(
                        tzinfo=timezone.utc
                    )
                    + timedelta(days=1)
                    - timedelta(seconds=1)
                )
                filters.append(Deal.created_at <= date_to)
            except ValueError:
                pass

        # ------------------- KANBAN VIEW PROCESSOR -------------------
        if kanban:
            # 1. First, build the clean query based on the active filters
            base_query = db.query(Deal).filter(and_(*filters))

            # 2. Get the actual total count of ALL matching data in DB (e.g., 220)
            total_count = base_query.count()

            # 3. Pull the specific entities, but CAP them at 200 items max
            deals = (
                base_query.with_entities(
                    Deal.id,
                    Deal.account_name,
                    Deal.lender_name,
                    Deal.deal_status,
                    Deal.loan_type,
                    Deal.deal_owner_id,
                    Deal.deal_expected_closing,
                    Deal.deal_status_closing,
                    Deal.lender_login_type,
                    Deal.partner_name,
                )
                .limit(200)
                .all()
            )  # <--- CHANGE IS HERE: Added .limit(200)

            # 4. Group your dataset by stage status (Will process max 200 items)
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

            # 5. Return matching the exact structure from your tickets controller
            return {"data": grouped, "page_info": {"total": total_count}}
        # ------------------- STANDARD / DRILLDOWN VIEWS -------------------
        base_query = db.query(Deal).filter(and_(*filters))

        # Single Deal Detail View Scenario
        if deal_id:
            deals = (
                base_query.options(selectinload(Deal.owner), selectinload(Deal.revenue))
                .limit(1)
                .all()
            )
            if deals:
                deal = deals[0]
                ids_list = [str(deal.id)]
                if getattr(deal, "crm_deal_id", None):
                    ids_list.append(str(deal.crm_deal_id))

                tickets_records = (
                    db.query(Ticket).filter(Ticket.deal_id == deal.id).all()
                )

                serialized_tickets = []
                for ticket in tickets_records:
                    ids_list.append(str(ticket.id))
                    t_dict = {
                        c.name: getattr(ticket, c.name)
                        for c in ticket.__table__.columns
                    }
                    for key in (
                        "id",
                        "deal_id",
                        "account_id",
                        "created_by",
                        "modified_by",
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
                        for key in (
                            "id",
                            "deal_id",
                            "owner_id",
                            "created_by",
                            "updated_by",
                        ):
                            if revenue_dict.get(key) is not None:
                                revenue_dict[key] = str(revenue_dict[key])

                        for key, val in revenue_dict.items():
                            if isinstance(val, (date, datetime)):
                                revenue_dict[key] = val.isoformat()
                            if isinstance(val, float):
                                revenue_dict[key] = str(val)

                        serialized_revenue.append(revenue_dict)

                notes = get_notes(
                    id_list=ids_list,
                    notes_collection=mongodb_conn["Notes"],
                    module_name=["Deals", "Tickets"],
                )

                deal_dict = {
                    c.name: getattr(deal, c.name) for c in deal.__table__.columns
                }
                deal_dict["id"] = str(deal.id)
                if deal.deal_owner_id:
                    deal_dict["deal_owner_id"] = str(deal.deal_owner_id)
                if deal.account_id:
                    deal_dict["account_id"] = str(deal.account_id)
                if deal.account and deal.account.account_name:
                    deal_dict["account_name"] = deal.account.account_name
                if deal.modified_by:
                    deal_dict["updated_by"] = str(deal.modified_by)

                deal_dict["modified_time"] = deal.updated_at
                deal_dict["modified_at"] = deal.updated_at
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

        # Standard List View Paginated Scenario
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
                Deal.partner_name,
                Deal.deal_expected_closing,
                Deal.deal_status_closing,
                Deal.deal_type,
                Deal.deal_call_back_datetime,
                Deal.amount_required,
                Deal.deal_name,
                Deal.created_at,
                Deal.updated_at,
                Deal.updated_at.label("modified_time"),
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


# --- Ensure this matches the bottom of your src/controllers/deals.py ---


def create_deal(deal, db: Session, user_id, user_role):
    try:
        # --- Duplicate deal check: same account + deal_type + loan_type ---
        if deal.deal_type and deal.loan_type:
            duplicate = (
                db.query(Deal)
                .filter(
                    Deal.account_id == int(deal.account_id),
                    Deal.deal_type == deal.deal_type,
                    Deal.loan_type == deal.loan_type,
                )
                .first()
            )
            if duplicate:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        'A similar deal with same "Deal Type" and "Type of Loan" already exist, '
                        'Please try changing the "Deal Type" and "Type of Loan" else refer to the existing deals'
                    ),
                )

        # --- Auto-generate deal_name: {account_name}/{account_id}/D{seq} ---
        existing_deal_count = (
            db.query(Deal)
            .filter(Deal.account_id == int(deal.account_id))
            .count()
        )
        existing_deal_count += 1
        sequence = str(existing_deal_count).zfill(4)
        generated_deal_name = (
            f"{deal.account_name}/DL/{sequence}"
        )

        created_deal = Deal(
            account_id=deal.account_id,
            account_name=deal.account_name,
            deal_name=generated_deal_name,
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
            partner_name=deal.partner_name,
        )
        db.add(created_deal)
        db.commit()
        db.refresh(created_deal)

        # 1. Audit Logging Serialization
        deal_dict = deal.model_dump()
        sanitized_payload = jsonable_encoder(deal_dict)

        log_action(
            db,
            user_id,
            user_role,
            "CREATED",
            "Deal",
            created_deal.id,
            sanitized_payload,
        )

        # ─── FIXED: CLEAN HARDCODED EMAIL TRIGGER BLOCK ───
        try:
            # Strictly dispatching to these 2 specific banking team mailboxes
            notification_emails = [
                "sutapa.roy@r1xchange.com",
                "pranay.kumar@r1xchange.com",
                "raj.nandini@r1xchange.com",
            ]

            # from src.controllers.Background_threads import BackgroundThreadPool
            # from src.controllers.mail import notify_deal_created_approval
            #
            # # Inform terminal precisely about the trigger firing
            # print(
            #     f"!!! DISPATCHING DEAL NOTIFICATION TO BANKING TEAM: {notification_emails} !!!"
            # )
            #
            # BackgroundThreadPool.execute_task(
            #     notify_deal_created_approval,
            #     notification_emails,
            #     created_deal.account_name or "Unknown Account",
            #     created_deal.id,
            # )
        except Exception as mail_trigger_err:
            print(f"Warning: Deal approval email trigger failed: {mail_trigger_err}")

        return created_deal

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail={"message": str(e)})


def update_deal_based_on_id(user_id, user_role, db: Session, deal_id: int, payload):
    db_deal = db.query(Deal).filter(Deal.id == deal_id).first()
    if not db_deal:
        raise HTTPException(status_code=404, detail={"msg": "Deal not found"})

    # --- Duplicate deal check on UPDATE: same account + deal_type + loan_type ---
    new_deal_type = payload.get("deal_type", db_deal.deal_type)
    new_loan_type = payload.get("loan_type", db_deal.loan_type)
    if new_deal_type and new_loan_type:
        duplicate = (
            db.query(Deal)
            .filter(
                Deal.account_id == db_deal.account_id,
                Deal.deal_type == new_deal_type,
                Deal.loan_type == new_loan_type,
                Deal.id != deal_id,  # exclude self
            )
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=409,
                detail=(
                    'A similar deal with same "Deal Type" and "Type of Loan" already exist, '
                    'Please try changing the "Deal Type" and "Type of Loan" else refer to the existing deals'
                ),
            )


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

        if user_id in MANAGERID.BYPASS_USER_IDS:
            pass
        elif role in ("super_admin", "admin"):
            pass

        elif role == "manager":
            allowed_owner_ids = [user_id] + MANAGER_EXECUTIVES_MAP.get(user_id, [])

        elif role == "executive":
            allowed_owner_ids = [user_id]

        if allowed_owner_ids is not None:
            filters.append(Deal.deal_owner_id.in_(allowed_owner_ids))
        # append the query-parameter
        filters.append(Deal.account_name.ilike(f"{deal_name.strip()}%"))

        data = db.query(Deal.id, Deal.account_name).filter(*filters)

        serialized_deals = []

        for deal in data:
            revenue_dict = {"id": str(deal.id), "account_name": deal.account_name}
            serialized_deals.append(revenue_dict)

        return {
            "success": True,
            "message": "Deal lookup fetched successfully",
            "data": serialized_deals,
        }
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Internal server error")


def update_and_insert_deals(insertion_deals, updation_deals, db: Session):
    from sqlalchemy.exc import SQLAlchemyError
    inserted = 0
    updated = 0
    failed_deals = []

    for deal_data in insertion_deals:
        try:
            # Check duplicate deal: same account + deal_type + loan_type
            dt_type = deal_data.get("deal_type")
            ln_type = deal_data.get("loan_type")
            if dt_type and ln_type:
                duplicate = (
                    db.query(Deal)
                    .filter(
                        Deal.account_id == deal_data["account_id"],
                        Deal.deal_type == dt_type,
                        Deal.loan_type == ln_type,
                    )
                    .first()
                )
                if duplicate:
                    raise ValueError(
                        'A similar deal with same "Deal Type" and "Type of Loan" already exist'
                    )

            # Auto-generate deal_name: {account_name}/{account_id}/D{seq}
            account_id = deal_data["account_id"]
            account_name = deal_data["account_name"]
            existing_deal_count = (
                db.query(Deal)
                .filter(Deal.account_id == account_id)
                .count()
            )
            sequence = existing_deal_count + 1
            deal_data["deal_name"] = f"{account_name}/{account_id}/D{sequence:02d}"

            new_deal = Deal(**deal_data)
            db.add(new_deal)
            db.commit()
            db.refresh(new_deal)
            inserted += 1
        except SQLAlchemyError as e:
            db.rollback()
            failed_deals.append({"type": "insert", "data": deal_data, "error": str(e)})
        except Exception as e:
            db.rollback()
            failed_deals.append({"type": "insert", "data": deal_data, "error": str(e)})

    for deal_data in updation_deals:
        try:
            deal = db.query(Deal).filter(Deal.id == deal_data["id"]).first()
            if not deal:
                raise ValueError("Deal ID not found")

            # Check duplicate deal: same account + deal_type + loan_type
            new_deal_type = deal_data.get("deal_type", deal.deal_type)
            new_loan_type = deal_data.get("loan_type", deal.loan_type)
            if new_deal_type and new_loan_type:
                duplicate = (
                    db.query(Deal)
                    .filter(
                        Deal.account_id == deal.account_id,
                        Deal.deal_type == new_deal_type,
                        Deal.loan_type == new_loan_type,
                        Deal.id != deal.id,
                    )
                    .first()
                )
                if duplicate:
                    raise ValueError(
                        'A similar deal with same "Deal Type" and "Type of Loan" already exist'
                    )

            for key, value in deal_data.items():
                if key == "id":
                    continue
                setattr(deal, key, value)

            try:
                db.commit()
                db.refresh(deal)
                updated += 1
            except SQLAlchemyError as e:
                raise e
        except Exception as e:
            db.rollback()
            failed_deals.append(
                {"type": "update", "id": deal_data.get("id"), "error": str(e)}
            )

    return {"inserted": inserted, "updated": updated, "failed": failed_deals}


async def update_deals_based_on_csv(file: UploadFile, db: Session, user_id: int, user_role: str):
    import csv
    import io
    from starlette.responses import JSONResponse
    from src.models.account import Account
    from src.utility.utils import get_deal_headers
    from decimal import Decimal
    
    insertion_deals, updation_deals, error_list = [], [], []
    row_number = 1

    allowed_owner_ids = None
    if user_role == "manager":
        allowed_owner_ids = {int(user_id)} | set(
            MANAGERID.MANAGER_EXECUTIVES_MAP.get(int(user_id), [])
        )

    # Date fields that must be YYYY-MM-DD
    DATE_FIELDS = {
        "deal_expected_closing",
        "deal_status_closing"
    }

    # Integer fields
    INT_FIELDS = {
        "id",
        "account_id",
        "deal_owner_id",
    }

    # Numeric (Decimal) fields
    DECIMAL_FIELDS = {
        "disbursed_amount",
        "sanction_amount",
        "approved_amount",
        "amount_required",
        "processing_fees",
        "mm_charges",
        "insurance_amount",
        "pf_percentage",
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

        deal_headers = get_deal_headers()
        csv_headers = {col.strip().lower() for col in (reader.fieldnames or [])}
        missing_headers = deal_headers - csv_headers
        if missing_headers:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Header mismatch found",
                    "missing_headers": sorted(missing_headers),
                },
            )

        for row in data:
            row_number += 1
            try:
                # Normalise keys to lowercase; strip whitespace from values.
                # Empty / whitespace-only values become None (saved as NULL in DB).
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

                # Parse Date fields (expected YYYY-MM-DD)
                for field in DATE_FIELDS:
                    if row.get(field):
                        try:
                            row[field] = date.fromisoformat(row[field][:10])
                        except ValueError:
                            raise ValueError(f"Invalid date for {field}: '{row[field]}'; expected YYYY-MM-DD")

                # Parse Datetime fields
                if row.get("deal_call_back_datetime"):
                    try:
                        row["deal_call_back_datetime"] = datetime.strptime(
                            row["deal_call_back_datetime"], "%Y-%m-%d %H:%M"
                        )
                    except ValueError:
                        try:
                            # Fallback if already ISO
                            row["deal_call_back_datetime"] = datetime.fromisoformat(row["deal_call_back_datetime"])
                        except ValueError:
                            raise ValueError(
                                f"Invalid deal_call_back_datetime '{row['deal_call_back_datetime']}'; expected YYYY-MM-DD HH:MM"
                            )

                # Process parent ID (account_id)
                acc_id = row.pop("account_id", None)

                if user_role == "manager":
                    new_owner_id = row.get("deal_owner_id")
                    if new_owner_id and int(new_owner_id) not in allowed_owner_ids:
                        raise HTTPException(
                            status_code=403,
                            detail=f"Row {row_number}: You do not have permission to assign a deal to owner ID {new_owner_id}"
                        )

                # Validation based on if it's new or update
                if is_new:
                    if not acc_id:
                        raise ValueError("Parent ID (account_id) is required for new deals")

                    # Fetch account to verify it exists and get account_name
                    account = db.query(Account).filter(Account.id == acc_id).first()
                    if not account:
                        raise ValueError(f"Account with ID {acc_id} not found")

                    row["account_id"] = account.id
                    row["account_name"] = account.account_name
                    row.pop("id", None)
                    row["deal_owner_id"] = row.get("deal_owner_id") or user_id
                    row["created_by"] = int(user_id)
                    row["modified_by"] = int(user_id)
                    insertion_deals.append(row)
                else:
                    existing_deal = db.query(Deal).filter(Deal.id == row["id"]).first()
                    if not existing_deal:
                        raise ValueError(f"Deal with ID {row['id']} not found")
                    if user_role == "manager":
                        if existing_deal.deal_owner_id is not None and int(existing_deal.deal_owner_id) not in allowed_owner_ids:
                            raise HTTPException(
                                status_code=403,
                                detail=f"Row {row_number}: You do not have permission to update deal owned by user ID {existing_deal.deal_owner_id}"
                            )
                    if acc_id:
                        # If account_id is provided, let's verify the account exists
                        account = db.query(Account).filter(Account.id == acc_id).first()
                        if not account:
                            raise ValueError(f"Account with ID {acc_id} not found")
                        row["account_id"] = account.id
                        row["account_name"] = account.account_name
                    row["modified_by"] = int(user_id)
                    updation_deals.append(row)

            except HTTPException:
                raise
            except Exception as row_err:
                error_list.append({"row": row_number, "error": str(row_err)})

        if not insertion_deals and not updation_deals:
            return JSONResponse(
                status_code=200,
                content=jsonable_encoder({
                    "total_inserted": 0,
                    "total_updated": 0,
                    "row_errors": error_list,
                }),
            )

        db_result = update_and_insert_deals(
            insertion_deals, updation_deals, db
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

