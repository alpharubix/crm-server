import csv
import io
import logging
import math
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, UploadFile
from pymongo.synchronous.collection import Collection
from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.orm.attributes import flag_modified
from starlette.requests import Request
from starlette.responses import JSONResponse

import httpx
from src.config import settings

from src.controllers.audit_log import log_action
from src.controllers.auth import MANAGERID
# from src.controllers.Background_threads import BackgroundThreadPool
from src.controllers.notes import get_notes
from src.models.ticket import Ticket
from src.models.deal_document import DealDocument
from src.models.revenue import Revenue
from src.utility.utils import get_account_headers

from ..models.account import Account, AccountStatusHistory
from ..models.user import User
from ..schemas.account import AccountBase


def create_account(
    db: Session, data: AccountBase, user_id: int, user_role: str
) -> Account:
    if db.query(Account).filter(Account.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email exists")

    account_data = data.model_dump()
    account_data["created_by_id"] = user_id
    account_data["assignment_date"] = datetime.now(timezone.utc)

    # Validate owner assignment based on role
    new_owner_id = account_data.get("account_owner_id")
    if new_owner_id:
        if user_role == "manager":
            allowed_owner_ids = [user_id] + MANAGERID().MANAGER_EXECUTIVES_MAP.get(user_id, [])
            if int(new_owner_id) not in allowed_owner_ids:
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to assign an account to this owner"
                )
        elif user_role == "executive":
            if int(new_owner_id) != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to assign an account to this owner"
                )

    if data.created_time:
        account_data["created_time"] = data.created_time

    valid_keys = set(Account.__mapper__.attrs.keys())
    filtered_data = {k: v for k, v in account_data.items() if k in valid_keys}

    new_account = Account(**filtered_data)
    db.add(new_account)
    db.flush()

    history = AccountStatusHistory(
        account_id=new_account.id,
        old_status=None,
        new_status=new_account.account_status,
        changed_by=user_id,
    )
    db.add(history)
    db.commit()
    db.refresh(new_account)

    log_action(
        db,
        user_id,
        user_role,
        "CREATED",
        "Account",
        new_account.id,
        data.model_dump(mode="json"),
    )

    # --- NEW: ACCOUNT CREATED NOTIFICATION ROUTINE ---
    # owner = new_account.owner
    # if owner and owner.email:
    #     notification_emails = [owner.email]

    #     # Look up Reporting Manager via your class dictionary mapping configuration
    #     MANAGER_EXECUTIVES_MAP = MANAGERID().MANAGER_EXECUTIVES_MAP
    #     reporting_manager_id = None

    #     # Traverse map keys (managers) to find which array contains this owner's ID
    #     for mgr_id, executive_ids in MANAGER_EXECUTIVES_MAP.items():
    #         if owner.id in executive_ids:
    #             reporting_manager_id = mgr_id
    #             break

    #     if reporting_manager_id:
    #         manager_user = (
    #             db.query(User).filter(User.id == reporting_manager_id).first()
    #         )
    #         if manager_user and manager_user.email:
    #             notification_emails.append(manager_user.email)

        # Offload safely into your Background Thread Pool
        # from src.controllers.mail import notify_account_assigned
        #
        # BackgroundThreadPool.execute_task(
        #     notify_account_assigned,
        #     list(set(notification_emails)),  # Duplication filtering safe safeguard
        #     owner.full_name,
        #     new_account.account_name,
        #     new_account.id,
        # )

    return new_account


def update_account(
    db: Session, account_id: int, payload: Dict[str, Any], user_id: int, user_role: str
):
    db_account = db.query(Account).filter(Account.id == account_id).first()
    if not db_account:
        raise HTTPException(status_code=404, detail={"msg": "Account not found"})

    # Check if user has permission to update this account
    if user_role not in ("super_admin", "admin"):
        if user_role == "manager":
            allowed_owner_ids = [user_id] + MANAGERID().MANAGER_EXECUTIVES_MAP.get(user_id, [])
        elif user_role == "executive":
            allowed_owner_ids = [user_id]
        else:
            allowed_owner_ids = []
        
        if db_account.account_owner_id is not None and db_account.account_owner_id not in allowed_owner_ids:
            raise HTTPException(
                status_code=403,
                detail="You do not have permission to update this account"
            )

    old_status = db_account.account_status
    old_owner_id = db_account.account_owner_id

    account_name_changed = False
    new_account_name = payload.get("account_name")
    if new_account_name is not None and new_account_name != db_account.account_name:
        account_name_changed = True

    custom_fields_dict = dict(db_account.custom_fields or {})
    jsonb_columns = [
        "business_details",
        "business_premise_address",
        "applicant_residence_address",
        "co_applicant_residence_address",
        "customer_references",
        "customer_salary_details",   # salary info for Salaried profile_type
    ]

    # Pure Date columns — must be parsed separately before the generic datetime branch
    DATE_ONLY_COLUMNS = {"source_date"}

    for key, value in payload.items():
        if hasattr(db_account, key):
            if value == "" or value is None:
                setattr(db_account, key, None)
            elif key in DATE_ONLY_COLUMNS:
                # Parse as a date-only value (YYYY-MM-DD string or already a date)
                if isinstance(value, str):
                    try:
                        value = date.fromisoformat(value[:10])
                    except ValueError as e:
                        raise HTTPException(
                            status_code=400,
                            detail={"message": f"Invalid date format for {key}: {str(e)}"},
                        )
                setattr(db_account, key, value)
            elif "time" in key or "date" in key:
                if isinstance(value, str):
                    try:
                        value = datetime.fromisoformat(value)
                        if value.tzinfo is None:
                            value = value.replace(tzinfo=timezone.utc)
                        if key == "call_back_date_time" and value < datetime.now(
                            timezone.utc
                        ):
                            raise HTTPException(
                                status_code=400,
                                detail={"message": "Date should not be in the past"},
                            )
                    except HTTPException:
                        raise
                    except Exception as e:
                        raise HTTPException(
                            status_code=400,
                            detail={"message": f"Invalid datetime format for {key}: {str(e)}"},
                        )
                setattr(db_account, key, value)
            elif key in jsonb_columns:
                current_dict = getattr(db_account, key) or {}
                if isinstance(value, dict) and isinstance(current_dict, dict):
                    updated_dict = {**current_dict, **value}
                    setattr(db_account, key, updated_dict)
                    flag_modified(db_account, key)
                else:
                    setattr(db_account, key, value)
            else:
                setattr(db_account, key, value)
        else:
            if value == "" or value is None:
                custom_fields_dict[key] = None
            else:
                custom_fields_dict[key] = value

    # Track ownership alterations explicitly before committing changes
    is_reassigned = False
    new_owner_id = payload.get("account_owner_id")
    if new_owner_id is not None and str(new_owner_id) != str(old_owner_id):
        if user_role == "manager":
            allowed_owner_ids = [user_id] + MANAGERID().MANAGER_EXECUTIVES_MAP.get(user_id, [])
            if int(new_owner_id) not in allowed_owner_ids:
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to assign an account to this owner"
                )
        elif user_role == "executive":
            if int(new_owner_id) != user_id:
                raise HTTPException(
                    status_code=403,
                    detail="You do not have permission to assign an account to this owner"
                )
        db_account.assignment_date = datetime.now(timezone.utc)
        is_reassigned = True

    db_account.custom_fields = custom_fields_dict
    flag_modified(db_account, "custom_fields")
    db_account.modified_by_id = user_id

    new_status = db_account.account_status
    if new_status != old_status:
        history = AccountStatusHistory(
            account_id=account_id,
            old_status=old_status,
            new_status=new_status,
            changed_by=user_id,
        )
        db.add(history)

    if account_name_changed and new_account_name:
        from src.models.deal import Deal

        db.query(Deal).filter(Deal.account_id == account_id).update(
            {"account_name": new_account_name}, synchronize_session=False
        )

    try:
        db.commit()
        db.refresh(db_account)
        log_action(db, user_id, user_role, "UPDATED", "Account", account_id, payload)

        # --- NEW: ACCOUNT REASSIGNMENT TRIGGER ROUTINE ---
        # if is_reassigned:
        #     new_owner = db.query(User).filter(User.id == int(new_owner_id)).first()
        #     if new_owner and new_owner.email:
        #         reassign_emails = [new_owner.email]

        #         # Fetch reporting manager mapping for the new owner assignment configuration
        #         MANAGER_EXECUTIVES_MAP = MANAGERID().MANAGER_EXECUTIVES_MAP
        #         reporting_manager_id = None
        #         for mgr_id, executive_ids in MANAGER_EXECUTIVES_MAP.items():
        #             if new_owner.id in executive_ids:
        #                 reporting_manager_id = mgr_id
        #                 break

        #         if reporting_manager_id:
        #             manager_user = (
        #                 db.query(User).filter(User.id == reporting_manager_id).first()
        #             )
        #             if manager_user and manager_user.email:
        #                 reassign_emails.append(manager_user.email)

                # from src.controllers.mail import notify_account_assigned
                #
                # BackgroundThreadPool.execute_task(
                #     notify_account_assigned,
                #     list(set(reassign_emails)),
                #     new_owner.full_name,
                #     db_account.account_name,
                #     db_account.id,
        return db_account
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")


async def get_all_accounts(
    request: Request,
    db: Session,
    mongodb: Collection,
    page: int,
    account_name: Optional[str] = None,
    account_id: Optional[list[str] | str | int] = None,
    account_status: Optional[list[str]] = None,
    account_stage: Optional[str] = None,
    source: Optional[list[str]] = None,
    type_of_business: Optional[str] = None,
    industry: Optional[list[str]] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    pincode: Optional[str] = None,
    waba_interested: Optional[bool] = None,
    business_status: Optional[str] = None,
    call_back_date_time: Optional[datetime] = None,
    account_owner_id: Optional[list[int]] = None,
    phone_number: Optional[str] = None,
    module: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
):
    MANAGER_EXECUTIVES_MAP = MANAGERID().MANAGER_EXECUTIVES_MAP

    limit = 30
    offset = (page - 1) * limit
    query = db.query(Account)
    filters = [or_(Account.company_id == 1, Account.company_id.is_(None))]
    user_id = request.state.user_id
    role = request.state.role
    single_id_request = False
    allowed_owner_ids = None

    # Internal server-to-server API call to Underwriting Tool Backend (localhost:5050)
    if module:
        try:
            uw_url = f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}/crm/accounts-filter"
            uw_params = {"module": module}
            if from_date:
                uw_params["from_date"] = from_date
            if to_date:
                uw_params["to_date"] = to_date

            async with httpx.AsyncClient(timeout=30) as client:
                uw_response = await client.get(uw_url, params=uw_params)

            if uw_response.status_code == 200:
                uw_data = uw_response.json().get("data", [])
                matching_acc_ids = [
                    doc.get("account_id") for doc in uw_data if doc.get("account_id") is not None
                ]
                if not matching_acc_ids:
                    return {
                        "data": [],
                        "page_info": {
                            "page": page,
                            "total_pages": 0,
                            "data_size": 0,
                        },
                    }
                valid_ids = [int(i) for i in matching_acc_ids if str(i).isdigit()]
                filters.append(Account.id.in_(valid_ids if valid_ids else matching_acc_ids))
            else:
                logging.error(f"Underwriting tool backend returned status {uw_response.status_code}: {uw_response.text}")
                return {
                    "data": [],
                    "page_info": {
                        "page": page,
                        "total_pages": 0,
                        "data_size": 0,
                    },
                }
        except Exception as e:
            logging.error(f"Failed to connect to underwriting tool backend: {e}")
            return {
                "data": [],
                "page_info": {
                    "page": page,
                    "total_pages": 0,
                    "data_size": 0,
                },
            }

    # Role Permissions
    if role in ("super_admin", "admin"):
        pass
    elif role == "manager":
        allowed_owner_ids = [user_id] + MANAGER_EXECUTIVES_MAP.get(user_id, [])
    elif role == "executive":
        allowed_owner_ids = [user_id]

    if allowed_owner_ids is not None:
        filters.append(Account.account_owner_id.in_(allowed_owner_ids))

    # Apply all optional filters
    if account_id is not None:
        if isinstance(account_id, list):
            valid_ids = [int(i) for i in account_id if str(i).isdigit()]
            filters.append(Account.id.in_(valid_ids if valid_ids else account_id))
            if len(account_id) == 1:
                single_id_request = True
        else:
            acc_id_val = int(account_id) if str(account_id).isdigit() else account_id
            filters.append(Account.id == acc_id_val)
            single_id_request = True
    if account_name:
        filters.append(Account.account_name.ilike(f"%{account_name.strip()}%"))
    if account_status:
        status_list = [s.strip() for s in (account_status if isinstance(account_status, list) else [account_status]) if s and s.strip()]
        if status_list:
            filters.append(
                or_(*[Account.account_status.ilike(f"{status}%") for status in status_list])
            )
    if account_stage:
        filters.append(Account.account_stage.ilike(f"{account_stage.strip()}%"))
    if source:
        source_list = [s.strip() for s in (source if isinstance(source, list) else [source]) if s and s.strip()]
        if source_list:
            filters.append(
                or_(*[Account.source.ilike(f"{src}%") for src in source_list])
            )
    if type_of_business:
        filters.append(Account.type_of_business == type_of_business)
    if industry:
        industry_list = [ind.strip() for ind in (industry if isinstance(industry, list) else [industry]) if ind and ind.strip()]
        if industry_list:
            filters.append(
                or_(*[Account.industry.ilike(ind) for ind in industry_list])
            )
    if city:
        filters.append(Account.city.ilike(f"%{city.strip()}%"))
    if state:
        filters.append(Account.state.ilike(f"%{state.strip()}%"))
    if pincode:
        filters.append(Account.pincode == pincode)
    if waba_interested is not None:
        filters.append(Account.waba_interested == waba_interested)
    if business_status:
        filters.append(Account.business_status == business_status)
    if call_back_date_time:
        filters.append(Account.call_back_date_time != None)
        filters.append(Account.call_back_date_time <= call_back_date_time)
    if phone_number and phone_number.strip():
        filters.append(
            or_(
                Account.phone.like(f"%{phone_number}%"),
                Account.phone.like(f"%91{phone_number}%"),
                Account.phone.like(f"%+91{phone_number}%"),
            )
        )
    if account_owner_id:
        owner_ids = [int(oid) for oid in (account_owner_id if isinstance(account_owner_id, list) else [account_owner_id]) if oid is not None]
        if owner_ids:
            if role in ("super_admin", "admin"):
                filters.append(Account.account_owner_id.in_(owner_ids))
            else:
                allowed_set = {int(x) for x in (allowed_owner_ids or [])}
                if not all(oid in allowed_set for oid in owner_ids):
                    raise HTTPException(
                        status_code=403,
                        detail={
                            "message": "You do not have permission to access records for this owner",
                            "success": False,
                        },
                    )
                filters.append(Account.account_owner_id.in_(owner_ids))

    if single_id_request:
        base_query = query.filter(and_(*filters)) if filters else query
        total_data_size = base_query.count()
        data = (
            base_query.offset(offset)
            .options(
                selectinload(Account.owner),
                selectinload(Account.created_by),
                selectinload(Account.account_linked_contact),
                selectinload(Account.deals),
                selectinload(Account.modified_by)
            )
            .limit(limit)
            .all()
        )

        if len(data) != 0:
            note_pairs = []
            acc: Account = data[0]

            # Step 1: Add Parent Account to filter
            note_pairs.append({"Parent_Id.id": str(acc.id), "module": "Accounts"})

            # Step 2: Collect contact pairs
            for contact in acc.account_linked_contact:
                note_pairs.append(
                    {"Parent_Id.id": str(contact.id), "module": "Contacts"}
                )

            # Step 3: Collect deal IDs and pairs
            deal_ids_for_tickets = []
            for deal in acc.deals:
                note_pairs.append({"Parent_Id.id": str(deal.id), "module": "Deals"})
                deal_ids_for_tickets.append(deal.id)
                if deal.crm_deal_id:
                    note_pairs.append(
                        {"Parent_Id.id": str(deal.crm_deal_id), "module": "Deals"}
                    )

            # Step 4: Query tickets, documents, and revenue for deal hierarchy
            tickets_by_deal: dict[int, list] = {}
            tickets_list: list = []
            documents_list: list = []
            revenue_list: list = []

            if deal_ids_for_tickets:
                deal_map = {deal.id: getattr(deal, "deal_name", None) or getattr(deal, "account_name", None) or f"Deal #{deal.id}" for deal in acc.deals}

                # 4a. Tickets
                ticket_records = (
                    db.query(Ticket)
                    .filter(Ticket.deal_id.in_(deal_ids_for_tickets))
                    .all()
                )
                for ticket in ticket_records:
                    note_pairs.append(
                        {"Parent_Id.id": str(ticket.id), "module": "Tickets"}
                    )
                    t_dict = {
                        c.name: getattr(ticket, c.name)
                        for c in ticket.__table__.columns
                    }
                    t_dict["id"] = str(t_dict["id"])
                    t_dict["deal_id"] = str(t_dict["deal_id"])
                    t_dict["deal_name"] = deal_map.get(ticket.deal_id, "—")
                    tickets_by_deal.setdefault(ticket.deal_id, []).append(t_dict)
                    tickets_list.append(t_dict)

                # 4b. Deal Documents
                doc_records = (
                    db.query(DealDocument)
                    .filter(DealDocument.deal_id.in_(deal_ids_for_tickets))
                    .all()
                )
                for doc in doc_records:
                    d_dict = {
                        c.name: getattr(doc, c.name)
                        for c in doc.__table__.columns
                    }
                    d_dict["id"] = str(d_dict["id"])
                    d_dict["deal_id"] = str(d_dict["deal_id"])
                    d_dict["deal_name"] = deal_map.get(doc.deal_id, "—")
                    documents_list.append(d_dict)

                # 4c. Revenue
                rev_records = (
                    db.query(Revenue)
                    .filter(Revenue.deal_id.in_(deal_ids_for_tickets))
                    .all()
                )
                for rev in rev_records:
                    r_dict = {
                        c.name: getattr(rev, c.name)
                        for c in rev.__table__.columns
                    }
                    r_dict["id"] = str(r_dict["id"])
                    r_dict["deal_id"] = str(r_dict["deal_id"])
                    r_dict["deal_name"] = deal_map.get(rev.deal_id, "—")
                    revenue_list.append(r_dict)

            # Step 5: Attach enriched lists to account
            for deal in acc.deals:
                deal._tickets_list = tickets_by_deal.get(deal.id, [])

            acc._tickets_list = tickets_list
            acc._deal_documents_list = documents_list
            acc._revenue_list = revenue_list

            # Step 6: Fetch notes with paired filters
            acc.notes = get_notes(
                pair_filters=note_pairs, notes_collection=mongodb["Notes"]
            )

        total_pages = math.ceil(total_data_size / limit)
        return {
            "data": data,
            "page_info": {
                "page": page,
                "total_pages": total_pages,
                "data_size": total_data_size,
            },
        }

    else:
        # Standard list view query
        data = (
            db.query(
                Account.id,
                Account.account_name,
                Account.account_owner_id,
                Account.account_status,
                Account.source,
                Account.type_of_business,
                Account.industry,
                Account.state,
                Account.city,
                Account.call_back_date_time,
                Account.phone,
                Account.account_stage,
                Account.business_status,
                Account.is_priority_account,
                Account.source_date,
                Account.source_type,
                Account.assignment_date,
                Account.modified_time
            )
            .filter(and_(*filters))
            .offset(offset)
            .limit(limit)
            .all()
        )
        total_data_size = query.filter(*filters).count()
        total_pages = math.ceil(total_data_size / limit)
        return {
            "data": data,
            "page_info": {
                "page": page,
                "total_pages": total_pages,
                "data_size": total_data_size,
            },
        }


def get_account_by_id(db: Session, account_id: int) -> Account:
    account = db.query(Account).filter(Account.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


# Account_Status_history i.e trackin of acc history by id
def get_account_status_history(db: Session, account_id: int, page: int = 1):
    limit = 20
    offset = (page - 1) * limit

    history = (
        db.query(AccountStatusHistory)
        .filter(AccountStatusHistory.account_id == account_id)
        .options(joinedload(AccountStatusHistory.changed_by_user))
        .order_by(AccountStatusHistory.changed_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    if not history:
        raise HTTPException(
            status_code=404, detail="No status history found for this account"
        )
    return history


async def accounts_csv_update(file: UploadFile, db: Session):
    import pandas as pd
    try:
        if file.filename.endswith(".csv"):
            # if the file is csv file process the file
            contents = await file.read()
            csv_data = io.BytesIO(contents)
            df = pd.read_csv(csv_data)
            data = df.to_dict(orient="records")
            if len(data) == 0:
                return JSONResponse(
                    status_code=400, content={"message": "At least 1 row is required"}
                )
            # after getting the data check the headers
            required_headers = {"id", "account_owner_id"}
            csv_headers = set(data[0].keys())
            if required_headers != csv_headers:
                return JSONResponse(
                    status_code=400, content={"message": "Excel headers mismatch found"}
                )
            db.bulk_update_mappings(Account, data)
            db.commit()
            return JSONResponse(
                status_code=200,
                content={"message": f"{len(data)} accounts updated successfully"},
            )
        else:
            return JSONResponse(status_code=422, content="Only csv files are supported")
    except Exception as e:
        print(e)
        db.rollback()
        logging.exception("CSV account update failed")
        raise HTTPException(
            status_code=500, detail={"message": "Error processing CSV file"}
        )


def fetch_account_id(account_name: str, db: Session):
    try:
        results = (
            db.query(Account.id.label("id"), Account.account_name.label("account_name"))
            .filter(Account.account_name.ilike(f"%{account_name.strip()}%"))
            .limit(10)
            .all()
        )
        if len(results) == 0:
            return JSONResponse(status_code=404, content={"data": []})
        # Convert to list of dicts
        dict_results = [row._asdict() for row in results]
        return {"data": dict_results}
    except Exception as e:
        logging.exception(e)
        raise HTTPException(
            status_code=500, detail={"message": "Internal server error"}
        )


# JSONB columns that must be merged (not overwritten) when updating via CSV
_JSONB_MERGE_KEYS = {"business_premise_address", "business_details"}


def update_and_insert_accounts(insertion_accounts, updation_accounts, db: Session):
    inserted = 0
    updated = 0
    failed_accounts = []

    for acc in insertion_accounts:
        try:
            account = Account(**acc)
            db.add(account)
            db.commit()
            db.refresh(account)
            inserted += 1
        except SQLAlchemyError as e:
            db.rollback()
            failed_accounts.append({"type": "insert", "data": acc, "error": str(e)})

    for acc in updation_accounts:
        try:
            account = db.query(Account).filter(Account.id == acc["id"]).first()
            if not account:
                raise ValueError("Account ID not found")

            for key, value in acc.items():
                if key == "id":
                    continue
                if key in _JSONB_MERGE_KEYS:
                    # Merge CSV-supplied keys into the existing JSONB, preserving
                    # any other keys already stored (e.g. industry inside business_details)
                    existing = getattr(account, key) or {}
                    merged = {**existing, **value}
                    setattr(account, key, merged)
                    flag_modified(account, key)
                else:
                    setattr(account, key, value)
            try:
                db.commit()
                db.refresh(account)
                updated += 1
            except SQLAlchemyError as e:
                raise e
        except Exception as e:
            logging.exception(e)
            db.rollback()
            failed_accounts.append(
                {"type": "update", "id": acc.get("id"), "error": str(e)}
            )

    return {"inserted": inserted, "updated": updated, "failed": failed_accounts}


async def update_accounts_based_on_csv(file, db: Session, user_id: int, user_role: str):
    insertion_accounts, updation_accounts, error_list = [], [], []
    row_number = 1

    allowed_owner_ids = None
    if user_role == "manager":
        allowed_owner_ids = {int(user_id)} | set(
            MANAGERID.MANAGER_EXECUTIVES_MAP.get(int(user_id), [])
        )

    # CSV columns that map into business_premise_address JSONB {city, state, pincode}
    _BUSINESS_PREMISE_MAP = {
        "business_premise_city": "city",
        "business_premise_state": "state",
        "business_premise_pincode": "pincode",
    }
    # CSV columns that map into business_details JSONB
    _BUSINESS_DETAILS_KEYS = {"gstn", "pan"}

    try:
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="Only CSV files are supported")

        contents = await file.read()
        decoded = contents.decode("utf-8-sig", errors="replace").splitlines()
        reader = csv.DictReader(decoded)
        data = list(reader)

        if not data:
            raise HTTPException(status_code=400, detail="CSV file is empty")

        # Strict header validation — all required headers must be present;
        # report exactly which ones are missing so the user can fix the file.
        account_headers = get_account_headers()
        csv_headers = {col.strip().lower() for col in (reader.fieldnames or [])}
        missing_headers = account_headers - csv_headers
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

                # --- Type conversions ---

                if row.get("id"):
                    row["id"] = int(row["id"])

                if row.get("account_owner_id"):
                    row["account_owner_id"] = int(row["account_owner_id"])

                # source_date — must be YYYY-MM-DD
                if row.get("source_date"):
                    try:
                        row["source_date"] = date.fromisoformat(row["source_date"][:10])
                    except ValueError:
                        raise ValueError(
                            f"Invalid source_date '{row['source_date']}'; expected YYYY-MM-DD"
                        )

                # call_back_date_time — expected as 'YYYY-MM-DD HH:MM'
                if row.get("call_back_date_time"):
                    row["call_back_date_time"] = datetime.strptime(
                        row["call_back_date_time"], "%Y-%m-%d %H:%M"
                    )

                # waba_interested — truthy strings → True, empty → None
                waba_raw = row.get("waba_interested")
                if waba_raw is not None:
                    row["waba_interested"] = waba_raw.lower() in ["yes", "true", "1"]
                # else leaves as None — column is nullable

                # --- Build business_premise_address JSONB ---
                # Pop the three CSV keys and assemble into a nested dict.
                # If a value is None (blank in CSV), it is stored as None inside the JSONB.
                business_premise_address = {}
                for csv_key, db_key in _BUSINESS_PREMISE_MAP.items():
                    business_premise_address[db_key] = row.pop(csv_key, None)
                row["business_premise_address"] = business_premise_address

                # --- Build business_details JSONB ---
                business_details = {}
                for key in _BUSINESS_DETAILS_KEYS:
                    business_details[key] = row.pop(key, None)
                row["business_details"] = business_details

                if user_role == "manager":
                    new_owner_id = row.get("account_owner_id")
                    if new_owner_id and int(new_owner_id) not in allowed_owner_ids:
                        raise HTTPException(
                            status_code=403,
                            detail=f"Row {row_number}: You do not have permission to assign an account to owner ID {new_owner_id}"
                        )

                if is_new:
                    row.pop("id", None)
                    row["account_owner_id"] = row.get("account_owner_id") or user_id
                    row["created_by_id"] = int(user_id)
                    insertion_accounts.append(row)
                else:
                    existing_account = db.query(Account).filter(Account.id == row["id"]).first()
                    if not existing_account:
                        raise ValueError(f"Account with ID {row['id']} not found")
                    if user_role == "manager":
                        if existing_account.account_owner_id is not None and int(existing_account.account_owner_id) not in allowed_owner_ids:
                            raise HTTPException(
                                status_code=403,
                                detail=f"Row {row_number}: You do not have permission to update account owned by user ID {existing_account.account_owner_id}"
                            )
                    # Pass the full row (including None values) so blank CSV cells
                    # explicitly clear existing DB values, as requested.
                    updation_accounts.append(row)

            except HTTPException:
                raise
            except Exception as row_err:
                error_list.append({"row": row_number, "error": str(row_err)})

        if not insertion_accounts and not updation_accounts:
            return JSONResponse(
                status_code=200,
                content={
                    "total_inserted": 0,
                    "total_updated": 0,
                    "row_errors": error_list,
                },
            )

        db_result = update_and_insert_accounts(
            insertion_accounts, updation_accounts, db
        )
        return JSONResponse(
            status_code=200,
            content={
                "total_inserted": db_result["inserted"],
                "total_updated": db_result["updated"],
                "row_errors": error_list + db_result["failed"],
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"detail": f"Processing error: {str(e)}", "row_errors": error_list},
        )
