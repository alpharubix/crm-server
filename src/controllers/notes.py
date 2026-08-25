import re
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

# from fastapi.exceptions import HTTPException
from pymongo.synchronous.collection import Collection
from sqlalchemy import or_
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

from src.controllers import auth, mail
from src.database import SessionLocal
from src.models.account import Account
from src.models.contact import Contact
from src.models.deal import Deal
from src.models.ticket import Ticket
from src.models.user import User

from .audit_log import log_action
from src.controllers.Background_threads import BackgroundThreadPool

IST = ZoneInfo("Asia/Kolkata")


def insert_notes(user_id, user_role, note, parent_id, db, module_name, pg_db: Session, notes_parent_id: str | None = None):
    try:
        notes_coll = db["Notes"]

        # Look up user from PostgreSQL (source of truth) — not MongoDB users collection
        # MongoDB users collection may be missing HR-only users like Sarada/Ambika
        pg_user = (
            pg_db.query(User.id, User.full_name, User.email)
            .filter(User.id == int(user_id))
            .first()
        )
        if pg_user:
            Owner = {
                "id": str(pg_user.id),
                "first_name": pg_user.full_name,
                "email": pg_user.email,
            }
        else:
            Owner = None
        if module_name == "Accounts":
            raw_parent_acc = (
                pg_db.query(Account.id, Account.account_name)
                .filter(Account.id == int(parent_id))
                .first()
            )
            if not raw_parent_acc:
                return JSONResponse(
                    status_code=404,
                    content={"error": f"Account with id {parent_id} not found"},
                )
            Parent_Id = {
                "id": str(raw_parent_acc.id),
                "account_name": raw_parent_acc.account_name,
            }
        elif module_name == "Contacts":
            raw_parent_con = (
                pg_db.query(Contact.id, Contact.last_name)
                .filter(Contact.id == int(parent_id))
                .first()
            )
            if not raw_parent_con:
                return JSONResponse(
                    status_code=404,
                    content={"error": f"Contact with id {parent_id} not found"},
                )
            Parent_Id = {
                "id": str(raw_parent_con.id),
                "contact_name": raw_parent_con.last_name,
            }
        elif module_name == "Tickets":
            raw_parent_ticket = (
                pg_db.query(Ticket.id, Deal.account_name)
                .join(Deal, Ticket.deal_id == Deal.id)
                .filter(Ticket.id == int(parent_id))
                .first()
            )
            if not raw_parent_ticket:
                return JSONResponse(
                    status_code=404,
                    content={"error": f"Ticket with id {parent_id} not found"},
                )
            Parent_Id = {
                "id": str(raw_parent_ticket.id),
                "ticket_name": raw_parent_ticket.account_name,
            }
        elif module_name == "Job_Requirements":
            from src.models.hiring import JobRequirement

            raw_parent_jr = (
                pg_db.query(JobRequirement.id, JobRequirement.hiring_position)
                .filter(JobRequirement.id == int(parent_id))
                .first()
            )
            Parent_Id = {
                "id": str(raw_parent_jr.id),
                "job_requirement_name": raw_parent_jr.hiring_position
                if raw_parent_jr
                else "Unknown",
            }
        elif module_name == "Candidates":
            from src.models.hiring import Candidate

            raw_parent_can = (
                pg_db.query(Candidate.id, Candidate.candidate_name)
                .filter(Candidate.id == int(parent_id))
                .first()
            )
            Parent_Id = {
                "id": str(raw_parent_can.id),
                "candidate_name": raw_parent_can.candidate_name
                if raw_parent_can
                else "Unknown",
            }
        elif module_name in ["Account_Tasks", "AccountTasks", "AccountTask"]:
            from src.models.account_task import AccountTask

            p_int = int(parent_id) if str(parent_id).isdigit() else None
            raw_parent_task = (
                pg_db.query(AccountTask.id, AccountTask.task_type)
                .filter(or_(AccountTask.id == parent_id, AccountTask.id == p_int))
                .first()
            )
            Parent_Id = {
                "id": str(raw_parent_task.id) if raw_parent_task else str(parent_id),
                "task_name": f"Account Task #{raw_parent_task.id}"
                if raw_parent_task
                else "Account Task",
            }
        else:
            raw_parent_deal = (
                pg_db.query(Deal.id, Deal.deal_name)
                .filter(Deal.id == int(parent_id))
                .first()
            )
            Parent_Id = {
                "id": str(raw_parent_deal.id),
                "deal_name": raw_parent_deal.deal_name
                if raw_parent_deal
                else "Unknown",
            }
        Modified_By = None
        # Build Created_By from the same PG user data — no second DB call needed
        Created_By = (
            {"id": Owner["id"], "name": Owner["first_name"], "email": Owner["email"]}
            if Owner
            else None
        )

        now_iso = datetime.now(UTC).isoformat()
        note_doc = {
            "Owner": Owner,
            "Created_By": Created_By,
            "Modified_By": Modified_By,
            "Note_Content": note,
            "Parent_Id": Parent_Id,
            "module": module_name,
            "notesParentId": notes_parent_id,
            "Created_Time": now_iso,
            "Modified_Time": now_iso,
        }

        result = notes_coll.insert_one(note_doc)
        print("Insertion result", result)

        inserted_id = str(result.inserted_id)
        note_doc["_id"] = inserted_id

        # Format Created_Time / Modified_Time to readable string for response consistency
        try:
            dt = datetime.fromisoformat(now_iso).astimezone(IST)
            note_doc["Created_Time"] = dt.strftime("%d %b %Y, %I:%M %p")
            note_doc["Modified_Time"] = dt.strftime("%d %b %Y, %I:%M %p")
        except Exception:
            pass

        log_action(
            pg_db,
            user_id,
            user_role,
            "CREATED",
            "Note",
            int(parent_id),
            {"note": note, "parent_id": parent_id, "notesParentId": notes_parent_id},
        )

        creator_name = pg_user.full_name if pg_user else "A CRM User"
        BackgroundThreadPool.execute_task(
            mentions,
            note,
            module_name,
            parent_id,
            creator_name,
        )

        return JSONResponse(
            status_code=201,
            content={
                "message": "Note saved successfully",
                "data": note_doc,
            },
        )
    except Exception as e:
        print(e)
        return JSONResponse(status_code=500, content={"error": str(e)})


def get_notes(
    notes_collection: Collection,
    pair_filters: list[dict[str, str]] = None,
    id_list: Any = None,
    module_name: str | list[str] = None,
):
    try:
        filter_query = {}

        # 1. Handle the NEW paired filters (from the code I gave you)
        if pair_filters:
            filter_query = {"$or": pair_filters}

        # 2. Handle the OLD style (to fix the Internal Server Error in Deals/Contacts)
        elif id_list:
            filter_query = (
                {"Parent_Id.id": {"$in": id_list}}
                if isinstance(id_list, list)
                else {"Parent_Id.id": id_list}
            )
            if module_name:
                if isinstance(module_name, list):
                    filter_query["module"] = {"$in": module_name}
                else:
                    filter_query["module"] = module_name

        else:
            return []

        projection = {
            "_id": 1,
            "id": 1,
            "Owner": 1,
            "Note_Content": 1,
            "Parent_Id": 1,
            "Modified_By": 1,
            "Created_By": 1,
            "Created_Time": 1,
            "Modified_Time": 1,
            "module": 1,
            "notesParentId": 1,
        }

        notes_cursor = notes_collection.find(filter_query, projection)
        notes = []
        for note in notes_cursor:
            if "_id" in note:
                note["_id"] = str(note["_id"])
            if "notesParentId" not in note:
                note["notesParentId"] = None

            # Time formatting
            for time_key in ["Created_Time", "Modified_Time"]:
                if note.get(time_key):
                    val = note[time_key]
                    try:
                        dt = (
                            datetime.fromisoformat(val) if isinstance(val, str) else val
                        )
                        # assume UTC if timezone missing
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=UTC)

                        # convert to IST
                        dt = dt.astimezone(IST)

                        note[time_key] = dt.strftime("%d %b %Y, %I:%M %p")
                    except:
                        pass
            notes.append(note)
        return notes

    except Exception as e:
        print(f"Notes Error: {e}")
        return []


def map_user_name_with_id(note_text: str) -> str:
    pattern = r"zsu\[@user:(\d+)\]zsu|crm\[user#(\d+)#(\d+)\]crm|crm\[user#(\d+)\]crm"

    def replace(match):
        if match.group(1):  # zsu[@user:ID]zsu
            user_id = match.group(1)
        elif match.group(2):  # crm[user#ID#ID]crm
            user_id = match.group(2)
        elif match.group(4):  # crm[user#ID]crm
            user_id = match.group(4)
        else:
            return match.group(0)  # no user_id found, return original

        if not user_id:
            return match.group(0)

        user_id = int(user_id)

        return "@" + auth.users.get(user_id, str(user_id))

    return re.sub(pattern, replace, note_text)


def is_note_has_comment(note_text: str) -> bool:
    pattern = re.compile(r"crm\[user#(\d+)\]crm")
    return bool(pattern.search(note_text))


def mentions(note, module_name, parent_id, creator_name: str = "A CRM User"):
    try:  # check if the note_content have mentions in them
        is_note_there = is_note_has_comment(note)
        if is_note_there:  # mention is there in the comment
            pattern = re.compile(r"crm\[user#(\d+)\]crm")
            user_ids = pattern.findall(note)
            with SessionLocal() as db:
                users = (
                    db.query(User.id, User.full_name, User.email)
                    .filter(User.id.in_(user_ids))
                    .all()
                )

            email_list = []  # holds the list of emails_id of user with the msg
            for user in users:
                email_list.append(
                    {
                        "recipient_name": user.full_name,
                        "creator_name": creator_name,
                        "user_name": creator_name,
                        "user_email_address": user.email,
                        "module": module_name,
                        "entity_id": parent_id,
                        "note": map_user_name_with_id(note),
                    }
                )
            # after collection all the emails of the user time to prepare the body and send the email
            mail.process_mention_emails(email_list)
            print("All emails sent successfully")
            return
    except Exception as e:
        print(e)
        return
