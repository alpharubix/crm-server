import re
from datetime import datetime, timezone
from typing import Any, List, Dict
from fastapi.exceptions import HTTPException
from pymongo.synchronous.collection import Collection
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse
from src.database import SessionLocal
from src.models.user import User
from src.models.account import Account
from src.models.contact import Contact
from src.models.deal import Deal
from src.models.ticket import Ticket
from .audit_log import log_action
from zoneinfo import ZoneInfo
from src.controllers import auth,mail
from src.controllers.Background_threads import BackgroundThreadPool
IST = ZoneInfo("Asia/Kolkata")

def insert_notes(user_id, user_role, note, parent_id, db, module_name, pg_db: Session):
    try:
        user_coll = db["users"]
        notes_coll = db["Notes"]
        Owner = user_coll.find_one(
            {"id": str(user_id)}, {"_id": 0, "id": 1, "first_name": 1, "email": 1}
        )
        if module_name == 'Accounts':
            raw_parent_acc = pg_db.query(Account.id,Account.account_name).filter(Account.id == int(parent_id)).first()
            Parent_Id = {
                "id": str(raw_parent_acc.id),
                "account_name": raw_parent_acc.account_name,
            }
        elif module_name == 'Contacts':
            raw_parent_con = pg_db.query(Contact.id,Contact.last_name).filter(Contact.id == int(parent_id)).first()
            Parent_Id = {
                "id": str(raw_parent_con.id),
                "contact_name": raw_parent_con.last_name,
            }
        elif module_name == 'Tickets':
            raw_parent_ticket = pg_db.query(Ticket.id, Deal.account_name).join(Deal, Ticket.deal_id == Deal.id).filter(Ticket.id == int(parent_id)).first()
            Parent_Id = {
                "id": str(raw_parent_ticket.id),
                "ticket_name": raw_parent_ticket.account_name, # Storing account name for visual reference, or you can change this
            }
        else:
            raw_parent_deal = pg_db.query(Deal.id,Deal.account_name).filter(Deal.id == int(parent_id)).first()
            Parent_Id = {
                "id": str(raw_parent_deal.id),
                "deal_name": raw_parent_deal.account_name,
            }
        Modified_By = None
        Created_By = user_coll.find_one(
            {"id": str(user_id)}, {"_id": 0, "id": 1, "first_name": 1, "email": 1}
        )
        if Created_By and "first_name" in Created_By:
            Created_By["name"] = Created_By.pop("first_name")

        result = notes_coll.insert_one({
            "Owner": Owner,
            "Created_By": Created_By,
            "Modified_By": Modified_By,
            "Note_Content": note,
            "Parent_Id": Parent_Id,
            "module":module_name,
            "Created_Time": datetime.now(timezone.utc).isoformat(),
            "Modified_Time": datetime.now(timezone.utc).isoformat(),
        })
        print("Insertion result",result)

        log_action(
            pg_db,
            user_id,
            user_role,
            "CREATED",
            "Note",
            int(parent_id),
            {"note": note, "parent_id": parent_id},
        )
        #create a background worker to send mention emails in a separate eventloop
        BackgroundThreadPool.execute_task(
            mentions,
            note,
            module_name,
            parent_id,
        )

        return JSONResponse(
            status_code=201, content={"message": "Note saved successfully"}
        )
    except Exception as e:
        print(e)
        return JSONResponse(status_code=500, content={"error": str(e)})



def get_notes(
    notes_collection: Collection, 
    pair_filters: List[Dict[str, str]] = None, 
    id_list: Any = None, 
    module_name: str | list[str] = None
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
            "_id": 0,
            "Owner": 1,
            "Note_Content": 1,
            "Parent_Id": 1,
            "Modified_By": 1,
            "Created_By": 1,
            "Created_Time": 1,
            "Modified_Time": 1,
            "module": 1,
        }

        notes_cursor = notes_collection.find(filter_query, projection)
        notes = []
        for note in notes_cursor:
            # Time formatting
            for time_key in ["Created_Time", "Modified_Time"]:
                if note.get(time_key):
                    val = note[time_key]
                    try:
                        dt = datetime.fromisoformat(val) if isinstance(val, str) else val
                        note[time_key] = dt.strftime("%d %b %Y, %I:%M %p")
                    except:
                        pass
            notes.append(note)
        return notes

    except Exception as e:
        print(f"Notes Error: {e}")
        return []
def map_user_name_with_id(note_text:str)->str:
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


def mentions(note,module_name,parent_id):
    try:#check if the note_content have mentions in them
        is_note_there = is_note_has_comment(note)
        if is_note_there: #mention is there in the comment
            pattern = re.compile(r"crm\[user#(\d+)\]crm")
            user_ids = pattern.findall(note)
            with SessionLocal() as db:
                users = db.query(
                    User.id,
                    User.full_name,
                    User.email
                ).filter(User.id.in_(user_ids)).all()

            email_list = []  # holds the list of emails_id of user with the msg
            for user in users:
                email_list.append({
                    "user_name": user.full_name,
                    "user_email_address": user.email,
                    "module": module_name,
                    "entity_id": parent_id,
                    "note": map_user_name_with_id(note)
                })
            #after collection all the emails of the user time to prepare the body and send the email
            mail.process_mention_emails(email_list)
            print("All emails sent successfully")
            return None
    except Exception as e:
        print(e)
        return None