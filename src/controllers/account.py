import csv
import io
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pandas as pd
from fastapi import HTTPException, UploadFile
from pymongo.synchronous.collection import Collection
from sqlalchemy import and_, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.orm.attributes import flag_modified
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.controllers.audit_log import log_action
from src.controllers.auth import MANAGERID
from src.controllers.Background_threads import BackgroundThreadPool
from src.controllers.mail import notify_account_created
from src.controllers.notes import get_notes
from src.models.ticket import Ticket
from src.utility.utils import get_account_headers

from ..models.account import Account, AccountStatusHistory
from ..models.user import User
from ..schemas.account import AccountBase


def create_account(
    db: Session, data: AccountBase, user_id: int, user_role: str
) -> Account:
    if db.query(Account).filter(Account.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email exists")

    # 2. Convert Pydantic object entirely to primitive Python types (dicts, lists, strs)
    # This guarantees JSONB blocks serialize correctly into PostgreSQL
    account_data = data.model_dump()

    # 3. Override system-managed parameters safely
    account_data["created_by_id"] = user_id
    account_data["assignment_date"] = datetime.now(timezone.utc)

    # Handle incoming Pydantic datetime default quirks if needed
    if data.created_time:
        account_data["created_time"] = data.created_time

    # 4. Dynamically unpack the dictionary into your SQLAlchemy Model
    new_account = Account(**account_data)

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

    # send email to account owner in background
    owner = new_account.owner  # lazy-loads from the same session
    if owner and owner.email:
        creator = db.query(User).filter(User.id == user_id).first()
        print("creator details", creator)
        BackgroundThreadPool.execute_task(
            notify_account_created,
            owner.email,
            owner.full_name,
            new_account.account_name,
            new_account.id,
            new_account.account_status,
            new_account.account_stage,
            creator.full_name if creator else "CRM System",
        )

    return new_account


def get_all_accounts(
    request: Request,
    db: Session,
    mongodb: Collection,
    page: int,
    account_name: Optional[str] = None,
    account_id: Optional[int] = None,
    account_status: Optional[str] = None,
    account_stage: Optional[str] = None,
    source: Optional[str] = None,
    type_of_business: Optional[str] = None,
    industry: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    pincode: Optional[str] = None,
    waba_interested: Optional[bool] = None,
    business_status: Optional[str] = None,
    call_back_date_time: Optional[datetime] = None,
    account_owner_id: Optional[int] = None,
    phone_number: Optional[str] = None,
):
    MANAGER_EXECUTIVES_MAP = MANAGERID().MANAGER_EXECUTIVES_MAP

    limit = 30
    offset = (page - 1) * limit
    query = db.query(Account)
    filters = []
    user_id = request.state.user_id
    role = request.state.role
    single_id_request = False
    allowed_owner_ids = None

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
        filters.append(Account.id == account_id)
        single_id_request = True
    if account_name:
        filters.append(Account.account_name.ilike(f"%{account_name.strip()}%"))
    if account_status:
        filters.append(Account.account_status.ilike(f"{account_status.strip()}%"))
    if account_stage:
        filters.append(Account.account_stage.ilike(f"{account_stage.strip()}%"))
    if source:
        filters.append(Account.source.ilike(f"{source.strip()}%"))
    if type_of_business:
        filters.append(Account.type_of_business == type_of_business)
    if industry:
        filters.append(Account.industry == industry)
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
        if role in ("super_admin", "admin"):
            filters.append(Account.account_owner_id == int(account_owner_id))
        elif user_id not in MANAGER_EXECUTIVES_MAP:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "You do not have permission to access records for this owner",
                    "success": False,
                },
            )
        elif account_owner_id in MANAGER_EXECUTIVES_MAP.get(user_id):
            filters.append(Account.account_owner_id == int(account_owner_id))
        else:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "You do not have permission to access records for this owner",
                    "success": False,
                },
            )

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

            # Step 4: Query tickets and add to pairs
            tickets_by_deal: dict[int, list] = {}
            if deal_ids_for_tickets:
                ticket_records = (
                    db.query(Ticket)
                    .filter(Ticket.deal_id.in_(deal_ids_for_tickets))
                    .all()
                )
                for ticket in ticket_records:
                    # STRICTLY PAIR TICKET ID WITH TICKET MODULE
                    note_pairs.append(
                        {"Parent_Id.id": str(ticket.id), "module": "Tickets"}
                    )

                    ticket_dict = {
                        c.name: getattr(ticket, c.name)
                        for c in ticket.__table__.columns
                    }
                    ticket_dict["id"] = str(ticket_dict["id"])
                    ticket_dict["deal_id"] = str(ticket_dict["deal_id"])
                    tickets_by_deal.setdefault(ticket.deal_id, []).append(ticket_dict)

            # Step 5: Attach tickets to deals
            for deal in acc.deals:
                deal._tickets_list = tickets_by_deal.get(deal.id, [])

            # Step 6: Fetch notes with paired filters (This fixes your bug)
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


def update_account(
    db: Session, account_id: int, payload: Dict[str, Any], user_id: int, user_role: str
):
    db_account = db.query(Account).filter(Account.id == account_id).first()
    if not db_account:
        raise HTTPException(status_code=404, detail={"msg": "Account not found"})

    # 1. Capture old values before changes
    old_status = db_account.account_status
    old_owner_id = db_account.account_owner_id

    # Track if the account name is explicitly changing before we modify the model instance
    account_name_changed = False
    new_account_name = payload.get("account_name")
    if new_account_name is not None and new_account_name != db_account.account_name:
        account_name_changed = True

    custom_fields_dict = dict(db_account.custom_fields or {})

    # List of your JSONB columns to protect against full overwrites
    jsonb_columns = [
        "business_details",
        "business_premise_address",
        "applicant_residence_address",
        "co_applicant_residence_address",
        "customer_references",
    ]

    for key, value in payload.items():
        if hasattr(db_account, key):
            if value == "" or value is None:
                setattr(db_account, key, None)
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
                    except Exception as e:
                        raise e
                setattr(db_account, key, value)

            # FIX: If the field is one of our JSONB dictionaries, MERGE it instead of overwriting
            elif key in jsonb_columns:
                current_dict = getattr(db_account, key) or {}
                if isinstance(value, dict) and isinstance(current_dict, dict):
                    # Shallow merge incoming keys into existing dictionary
                    updated_dict = {**current_dict, **value}
                    setattr(db_account, key, updated_dict)
                    # Tell SQLAlchemy that this internal JSON dictionary was modified
                    flag_modified(db_account, key)
                else:
                    setattr(db_account, key, value)
            else:
                setattr(db_account, key, value)
        else:
            # Handle true ad-hoc custom fields falling back into custom_fields JSONB
            if value == "" or value is None:
                custom_fields_dict[key] = None
            else:
                custom_fields_dict[key] = value

    # 2. Assignment Date Logic
    if "account_owner_id" in payload:
        new_owner_val = payload["account_owner_id"]
        if new_owner_val is not None and str(new_owner_val) != str(old_owner_id):
            db_account.assignment_date = datetime.now(timezone.utc)

    db_account.custom_fields = custom_fields_dict
    flag_modified(db_account, "custom_fields")
    db_account.modified_by_id = user_id

    # 3. Status History
    new_status = db_account.account_status
    if new_status != old_status:
        history = AccountStatusHistory(
            account_id=account_id,
            old_status=old_status,
            new_status=new_status,
            changed_by=user_id,
        )
        db.add(history)

    # 4. CASCADE UPDATE TO DEALS: Keep denormalized deal names in sync
    if account_name_changed and new_account_name:
        from src.models.deal import (
            Deal,  # Local import protects against dependency loops
        )

        db.query(Deal).filter(Deal.account_id == account_id).update(
            {"account_name": new_account_name}, synchronize_session=False
        )

    try:
        db.commit()
        db.refresh(db_account)
        log_action(db, user_id, user_role, "UPDATED", "Account", account_id, payload)
        return db_account
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")


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
        print(results)
        if len(results) == 0:
            return JSONResponse(status_code=404, content={"data": []})
        # Convert to list of dicts
        dict_results = [row._asdict() for row in results]
        print(dict_results)
        return {"data": dict_results}
    except Exception as e:
        logging.exception(e)
        raise HTTPException(
            status_code=500, detail={"message": "Internal server error"}
        )


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
                setattr(account, key, value)
            try:
                db.commit()
                db.refresh(account)
                updated += 1
            except SQLAlchemyError as e:
                raise e
        except Exception as e:
            print(e, acc.get("id"))
            db.rollback()
            failed_accounts.append(
                {"type": "update", "id": acc.get("id"), "error": str(e)}
            )

    return {"inserted": inserted, "updated": updated, "failed": failed_accounts}


async def update_accounts_based_on_csv(file, db: Session, user_id: int):
    insertion_accounts, updation_accounts, error_list = [], [], []
    row_number = 1

    try:
        if not file.filename.endswith(".csv"):
            raise HTTPException(status_code=400, detail="only support csv file")

        contents = await file.read()
        decoded = contents.decode("utf-8-sig", errors="replace").splitlines()
        reader = csv.DictReader(decoded)
        data = list(reader)

        if not data:
            raise HTTPException(status_code=400, detail="Csv file is empty")

        # Header validation
        account_headers = get_account_headers()
        csv_headers = {col.strip().lower() for col in (reader.fieldnames or [])}
        if account_headers - csv_headers:
            raise HTTPException(
                status_code=400,
                detail=f"Header mismatch: {account_headers - csv_headers}",
            )

        for row in data:
            row_number += 1
            try:
                # Clean and identify row type
                row = {
                    k: (v.strip() if v and v.strip() else None) for k, v in row.items()
                }
                is_new = not row.get("id")

                # Type conversions
                if row.get("id"):
                    row["id"] = int(row["id"])

                if row.get("call_back_date_time"):
                    row["call_back_date_time"] = datetime.strptime(
                        row["call_back_date_time"], "%m/%d/%Y %H:%M"
                    )

                if row.get("waba_interested"):
                    val = row["waba_interested"].lower()
                    row["waba_interested"] = val in ["yes", "true", "1"]

                if is_new:
                    row.pop("id", None)
                    row["account_owner_id"] = row.get("account_owner_id") or user_id
                    row["created_by_id"] = int(user_id)
                    insertion_accounts.append(row)
                else:
                    updation_accounts.append(
                        {k: v for k, v in row.items() if v is not None}
                    )

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
