from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

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


from pymongo import MongoClient

monogodb = MongoClient(settings.MONGODB_URI)


def get_mongodb():
    db = monogodb["crm_dev"]
    try:
        yield db
    finally:
        pass


# Must be AFTER Base and engine are defined, and after all models are imported
# from src.models.audit_log import AuditLog

# Base.metadata.create_all(bind=engine)
