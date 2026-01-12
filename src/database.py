from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

# Format: postgresql://username:password@host:port/database_name
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# Dependency for routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


####################################################

# This is the standard pattern. get_db() ensures each request gets a fresh DB session that auto-closes after use.
# Why needed:

# Routes use db: Session = Depends(get_db)
# Handles connection cleanup automatically
# Prevents connection leaks

# This approach is recommended over manual session management.

####################################################

from pymongo import MongoClient

monogodb = MongoClient(settings.MONGODB_URI)


def get_mongodb():
    db = monogodb["crm_dev"]
    try:
        yield db
    finally:
        pass
