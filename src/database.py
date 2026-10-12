from datetime import UTC, datetime

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient, MongoClient
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

# --- PostgreSQL SQLAlchemy Setup ---
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Synchronous MongoDB Setup (Existing CRM collections & Notes) ---
monogodb = MongoClient(settings.MONGODB_URI)
mongodb_client = monogodb


def get_mongodb():
    db = monogodb["crm_dev"]
    try:
        yield db
    finally:
        pass


def get_master_invoice_database():
    db = monogodb["invoice_master"]
    try:
        yield db
    except Exception as e:
        raise e


# --- Asynchronous MongoDB Setup (WhatsApp Module) ---
_async_client: AsyncMongoClient | None = None


def utcnow() -> datetime:
    return datetime.now(UTC)


async def get_async_mongo_client() -> AsyncMongoClient:
    global _async_client
    if _async_client is None:
        _async_client = AsyncMongoClient(settings.MONGODB_URI)
    return _async_client


async def init_whatsapp_indexes(db) -> None:
    """Ensure indexes exist for conversations, messages, and templates."""
    # 1. conversations indexes
    await db.conversations.create_index(
        [
            ("customer_wa_id", ASCENDING),
            ("business_phone_number_id", ASCENDING),
        ],
        unique=True,
        name="uq_customer_business_conversation",
    )
    await db.conversations.create_index(
        [("last_message_at", DESCENDING)],
        name="ix_conversation_last_message",
    )
    await db.conversations.create_index(
        [("contact_id", ASCENDING)],
        name="ix_conversation_contact_id",
    )

    # 2. messages indexes
    await db.messages.create_index(
        [("wamid", ASCENDING)],
        unique=True,
        partialFilterExpression={"wamid": {"$type": "string"}},
        name="uq_message_wamid",
    )
    await db.messages.create_index(
        [
            ("conversation_id", ASCENDING),
            ("timestamp", DESCENDING),
            ("_id", DESCENDING),
        ],
        name="ix_conversation_messages_timeline",
    )

    # 3. templates indexes
    await db.templates.create_index(
        [
            ("waba_id", ASCENDING),
            ("name", ASCENDING),
            ("language", ASCENDING),
        ],
        unique=True,
        name="uq_template_language",
    )


async def connect_whatsapp_db():
    client = await get_async_mongo_client()
    db = client["crm_dev"]
    await init_whatsapp_indexes(db)
    return db


def get_whatsapp_db():
    global _async_client
    if _async_client is None:
        _async_client = AsyncMongoClient(settings.MONGODB_URI)
    return _async_client["crm_dev"]


async def close_whatsapp_db() -> None:
    global _async_client
    if _async_client is not None:
        await _async_client.close()
        _async_client = None
