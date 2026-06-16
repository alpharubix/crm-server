import time

from pymongo import MongoClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

# ── PostgreSQL Connection Pool ──────────────────────────────────────────────
# pool_size=10        : keep 10 persistent connections open
# max_overflow=20     : allow 20 extra burst connections under peak load
# pool_timeout=30     : wait max 30s before raising "QueuePool limit" error
# pool_pre_ping=True  : test connection health before use (avoids stale conn errors)
# pool_recycle=1800   : recycle connections every 30 min (prevents idle timeouts)
engine = create_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_pre_ping=True,
    pool_recycle=1800,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start_time", []).append(time.time())


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - conn.info["query_start_time"].pop()

    if total > 0.05:  # log queries slower than 50ms
        print(f"\n[SLOW QUERY] {total:.3f}s")
        print(statement[:300])
        print("PARAMS:", parameters)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── MongoDB Connection Pool ─────────────────────────────────────────────────
# maxPoolSize=20      : keep up to 20 pooled connections to MongoDB
# connectTimeoutMS    : fail fast if MongoDB is unreachable
# serverSelectionTimeoutMS: don't hang forever on replica set elections
mongodb_client = MongoClient(
    settings.MONGODB_URI,
    maxPoolSize=20,
    connectTimeoutMS=5000,
    serverSelectionTimeoutMS=5000,
)


def get_mongodb():
    db = mongodb_client["crm_dev"]
    try:
        yield db
    finally:
        pass


# Base.metadata.create_all(bind=engine)
