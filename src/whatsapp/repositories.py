from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo.errors import DuplicateKeyError

from src.database import get_whatsapp_db, utcnow

STATUS_SEVERITY_ORDER = {
    "pending": 0,
    "sent_to_meta": 1,
    "sent": 2,
    "delivered": 3,
    "read": 4,
    "received": 4,
    "failed": 5,
}


def normalize_doc(doc: dict | None) -> dict | None:
    if not doc:
        return None
    d = dict(doc)
    if "_id" in d and isinstance(d["_id"], ObjectId):
        d["id"] = str(d["_id"])
        d["_id"] = str(d["_id"])
    if "conversation_id" in d and isinstance(d["conversation_id"], ObjectId):
        d["conversation_id"] = str(d["conversation_id"])
    return d


class WhatsAppRepository:
    def __init__(self, db=None):
        self._db = db

    @property
    def db(self):
        if self._db is not None:
            return self._db
        return get_whatsapp_db()

    # -------------------------------------------------------------------------
    # CONVERSATIONS
    # -------------------------------------------------------------------------

    async def get_or_create_conversation(
        self,
        customer_wa_id: str,
        business_phone_number_id: str,
        contact_id: int | None = None,
        customer_name: str | None = None,
    ) -> dict:
        """Find existing conversation or create a new one atomically."""
        filter_q = {
            "customer_wa_id": customer_wa_id,
            "business_phone_number_id": business_phone_number_id,
        }

        existing = await self.db.conversations.find_one(filter_q)
        if existing:
            # If contact_id or customer_name now discovered and was missing, update it
            updates = {}
            if contact_id is not None and not existing.get("contact_id"):
                updates["contact_id"] = contact_id
            if customer_name and not existing.get("customer_name"):
                updates["customer_name"] = customer_name
            if updates:
                updates["updated_at"] = utcnow()
                await self.db.conversations.update_one(filter_q, {"$set": updates})
                existing = await self.db.conversations.find_one(filter_q)
            return normalize_doc(existing)

        now = utcnow()
        new_doc = {
            "customer_wa_id": customer_wa_id,
            "business_phone_number_id": business_phone_number_id,
            "contact_id": contact_id,
            "customer_name": customer_name,
            "status": "open",
            "assigned_to": None,
            "unread_count": 0,
            "last_message_id": None,
            "last_message_preview": None,
            "last_message_direction": None,
            "last_message_status": None,
            "last_message_at": now,
            "created_at": now,
            "updated_at": now,
        }

        try:
            res = await self.db.conversations.insert_one(new_doc)
            new_doc["_id"] = res.inserted_id
            return normalize_doc(new_doc)
        except DuplicateKeyError:
            found = await self.db.conversations.find_one(filter_q)
            return normalize_doc(found)

    async def get_conversation_by_id(self, conversation_id: str) -> dict | None:
        try:
            oid = ObjectId(conversation_id)
        except Exception:
            return None
        doc = await self.db.conversations.find_one({"_id": oid})
        return normalize_doc(doc)

    async def get_conversation_by_wa_id(
        self, customer_wa_id: str, business_phone_number_id: str
    ) -> dict | None:
        doc = await self.db.conversations.find_one(
            {
                "customer_wa_id": customer_wa_id,
                "business_phone_number_id": business_phone_number_id,
            }
        )
        return normalize_doc(doc)

    async def update_conversation_last_message(
        self,
        conversation_id: str | ObjectId,
        message_id: str | ObjectId,
        preview: str,
        direction: str,
        status: str,
        timestamp: datetime,
        increment_unread: bool = False,
    ) -> None:
        oid = (
            ObjectId(conversation_id)
            if isinstance(conversation_id, str)
            else conversation_id
        )
        mid = ObjectId(message_id) if isinstance(message_id, str) else message_id

        update_ops: dict[str, Any] = {
            "$set": {
                "last_message_id": str(mid),
                "last_message_preview": preview[:160] if preview else "",
                "last_message_direction": direction,
                "last_message_status": status,
                "last_message_at": timestamp,
                "updated_at": utcnow(),
            }
        }
        if increment_unread:
            update_ops["$inc"] = {"unread_count": 1}

        await self.db.conversations.update_one({"_id": oid}, update_ops)

    async def mark_conversation_read(self, conversation_id: str | ObjectId) -> None:
        oid = (
            ObjectId(conversation_id)
            if isinstance(conversation_id, str)
            else conversation_id
        )
        await self.db.conversations.update_one(
            {"_id": oid},
            {"$set": {"unread_count": 0, "updated_at": utcnow()}},
        )

    async def list_conversations(
        self,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
        unread_only: bool = False,
    ) -> tuple[list[dict], int]:
        filters: dict[str, Any] = {}
        if unread_only:
            filters["unread_count"] = {"$gt": 0}
        if search and search.strip():
            s = search.strip()
            filters["$or"] = [
                {"customer_wa_id": {"$regex": s, "$options": "i"}},
                {"customer_name": {"$regex": s, "$options": "i"}},
                {"last_message_preview": {"$regex": s, "$options": "i"}},
            ]

        total_count = await self.db.conversations.count_documents(filters)
        cursor = (
            self.db.conversations.find(filters)
            .sort("last_message_at", DESCENDING)
            .skip((page - 1) * limit)
            .limit(limit)
        )
        docs = []
        async for doc in cursor:
            docs.append(normalize_doc(doc))
        return docs, total_count

    # -------------------------------------------------------------------------
    # MESSAGES
    # -------------------------------------------------------------------------

    async def save_message(self, message_data: dict) -> dict:
        """Idempotently insert a message. If wamid exists, returns existing doc."""
        wamid = message_data.get("wamid")
        if wamid:
            existing = await self.db.messages.find_one({"wamid": wamid})
            if existing:
                return normalize_doc(existing)

        data = message_data.copy()
        if "conversation_id" in data and isinstance(data["conversation_id"], str):
            data["conversation_id"] = ObjectId(data["conversation_id"])
        if "_id" in data and isinstance(data["_id"], str):
            data["_id"] = ObjectId(data["_id"])

        if "created_at" not in data:
            data["created_at"] = utcnow()
        if "timestamp" not in data:
            data["timestamp"] = utcnow()
        if "status_updated_at" not in data:
            data["status_updated_at"] = utcnow()

        try:
            res = await self.db.messages.insert_one(data)
            data["_id"] = res.inserted_id
            return normalize_doc(data)
        except DuplicateKeyError:
            if wamid:
                found = await self.db.messages.find_one({"wamid": wamid})
                return normalize_doc(found)
            raise

    async def get_message_by_wamid(self, wamid: str) -> dict | None:
        doc = await self.db.messages.find_one({"wamid": wamid})
        return normalize_doc(doc)

    async def get_message_by_id(self, message_id: str) -> dict | None:
        try:
            oid = ObjectId(message_id)
        except Exception:
            return None
        doc = await self.db.messages.find_one({"_id": oid})
        return normalize_doc(doc)

    async def update_message_status(
        self,
        wamid: str,
        new_status: str,
        status_timestamp: datetime,
        error_details: dict | None = None,
        raw_status_event: dict | None = None,
    ) -> dict | None:
        """
        Updates status, appends to status_history, and prevents out-of-order status downgrades.
        (e.g., delivered must NOT downgrade an already 'read' message).
        """
        existing = await self.db.messages.find_one({"wamid": wamid})
        if not existing:
            return None

        current_status = existing.get("status", "pending")
        current_rank = STATUS_SEVERITY_ORDER.get(current_status, 0)
        new_rank = STATUS_SEVERITY_ORDER.get(new_status, 0)

        # Build status_history entry
        history_entry = {
            "status": new_status,
            "timestamp": status_timestamp,
        }
        if error_details:
            history_entry["error"] = error_details

        push_ops: dict[str, Any] = {"status_history": history_entry}
        set_ops: dict[str, Any] = {"status_updated_at": utcnow()}

        # Only update status field if new_rank >= current_rank or if it's failed
        if new_status == "failed" or new_rank >= current_rank:
            set_ops["status"] = new_status
            if error_details:
                set_ops["error"] = error_details

        if raw_status_event:
            set_ops["latest_status_event"] = raw_status_event

        updated = await self.db.messages.find_one_and_update(
            {"wamid": wamid},
            {"$set": set_ops, "$push": push_ops},
            return_document=ReturnDocument.AFTER,
        )
        return normalize_doc(updated)

    async def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int = 50,
        before_timestamp: datetime | None = None,
        before_id: str | None = None,
    ) -> list[dict]:
        """Fetch messages chronologically with cursor pagination."""
        try:
            cid = ObjectId(conversation_id)
        except Exception:
            return []

        filters: dict[str, Any] = {"conversation_id": cid}
        if before_timestamp and before_id:
            try:
                bid = ObjectId(before_id)
                filters["$or"] = [
                    {"timestamp": {"$lt": before_timestamp}},
                    {"timestamp": before_timestamp, "_id": {"$lt": bid}},
                ]
            except Exception:
                filters["timestamp"] = {"$lt": before_timestamp}
        elif before_timestamp:
            filters["timestamp"] = {"$lt": before_timestamp}

        cursor = (
            self.db.messages.find(filters)
            .sort([("timestamp", DESCENDING), ("_id", DESCENDING)])
            .limit(limit)
        )

        messages = []
        async for doc in cursor:
            messages.append(normalize_doc(doc))
        # Return in ascending order for UI chronological display
        messages.reverse()
        return messages

    async def get_messages_by_phone(
        self,
        phone: str,
        limit: int = 6,
        skip: int = 0,
        direction: str | None = None,
    ) -> tuple[list[dict], int]:
        """
        Fetch messages from MongoDB for an account phone number.
        Matches customer_wa_id against clean digits and 10-digit suffix.
        """
        clean_digits = "".join(filter(str.isdigit, str(phone or "")))
        if not clean_digits:
            return [], 0

        phone_10 = clean_digits[-10:] if len(clean_digits) >= 10 else clean_digits
        query: dict[str, Any] = {
            "$or": [
                {"customer_wa_id": clean_digits},
                {"customer_wa_id": f"91{phone_10}"},
                {"customer_wa_id": phone_10},
                {"customer_wa_id": {"$regex": f"{phone_10}$"}},
            ]
        }
        if direction and direction in ("inbound", "outbound"):
            query["direction"] = direction

        total_count = await self.db.messages.count_documents(query)
        cursor = (
            self.db.messages.find(query)
            .sort([("timestamp", DESCENDING), ("created_at", DESCENDING), ("_id", DESCENDING)])
            .skip(skip)
            .limit(limit)
        )

        messages = []
        async for doc in cursor:
            norm = normalize_doc(doc)
            if norm:
                # If template body text wasn't rendered inline, enrich from db.templates
                if norm.get("type") == "template" and not norm.get("content", {}).get("rendered", {}).get("body"):
                    tmpl_name = norm.get("content", {}).get("template_name")
                    if tmpl_name:
                        tmpl = await self.db.templates.find_one({"name": tmpl_name})
                        if tmpl and tmpl.get("components"):
                            body_comp = next((c for c in tmpl["components"] if c.get("type") == "BODY"), None)
                            if body_comp:
                                norm.setdefault("content", {})
                                norm["content"].setdefault("rendered", {})
                                norm["content"]["rendered"]["body"] = body_comp.get("text", "")
                messages.append(norm)

        return messages, total_count

    # -------------------------------------------------------------------------
    # TEMPLATES
    # -------------------------------------------------------------------------

    async def upsert_template(self, template_data: dict) -> dict:
        waba_id = template_data["waba_id"]
        name = template_data["name"]
        language = template_data["language"]

        filter_q = {"waba_id": waba_id, "name": name, "language": language}
        now = utcnow()

        update_doc = template_data.copy()
        update_doc["updated_at"] = now
        update_doc["synced_at"] = now

        doc = await self.db.templates.find_one_and_update(
            filter_q,
            {"$set": update_doc},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return normalize_doc(doc)

    async def get_template(self, waba_id: str, name: str, language: str) -> dict | None:
        doc = await self.db.templates.find_one(
            {"waba_id": waba_id, "name": name, "language": language}
        )
        return normalize_doc(doc)

    async def list_templates(self, waba_id: str | None = None) -> list[dict]:
        filters = {}
        if waba_id:
            filters["waba_id"] = waba_id
        cursor = self.db.templates.find(filters).sort("name", ASCENDING)
        docs = []
        async for doc in cursor:
            docs.append(normalize_doc(doc))
        return docs
