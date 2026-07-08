import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from src.database import Base, get_db, get_mongodb, mongodb_client
from src.config import settings
from src.models.user import User
from src.utility.utils import get_jwt_token, get_hashed_password
from main import app
from fastapi.testclient import TestClient

# Parse current database_url to dynamically build a test database URL
db_url = settings.database_url
if "/" in db_url.split("://")[-1]:
    base_url, db_name = db_url.rsplit("/", 1)
    if "?" in db_name:
        db_name_only, query = db_name.split("?", 1)
        test_db_url = f"{base_url}/{db_name_only}_test?{query}"
        test_db_name = f"{db_name_only}_test"
    else:
        test_db_url = f"{base_url}/{db_name}_test"
        test_db_name = f"{db_name}_test"
else:
    test_db_url = db_url + "_test"
    test_db_name = "crm_test"

def create_test_db():
    if "postgresql" in settings.database_url:
        # Connect to 'postgres' DB on the same server to execute CREATE DATABASE
        postgres_url = f"{base_url}/postgres"
        if "?" in db_name and "query" in locals():
            postgres_url = f"{postgres_url}?{query}"
            
        temp_engine = create_engine(postgres_url, isolation_level="AUTOCOMMIT")
        with temp_engine.connect() as conn:
            try:
                conn.execute(text(f"CREATE DATABASE {test_db_name}"))
            except Exception:
                # Ignore if database already exists
                pass
        temp_engine.dispose()

@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    create_test_db()
    test_engine = create_engine(test_db_url)
    
    # Create all schemas
    Base.metadata.create_all(bind=test_engine)
    
    yield test_engine
    
    # Clean up connections
    test_engine.dispose()

@pytest.fixture(scope="function")
def db_session(setup_test_database):
    test_engine = setup_test_database
    connection = test_engine.connect()
    transaction = connection.begin()
    
    SessionLocalTest = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=connection,
    )
    session = SessionLocalTest()
    
    # Override get_db
    def override_get_db():
        try:
            yield session
        finally:
            pass
            
    app.dependency_overrides[get_db] = override_get_db
    
    yield session
    
    session.close()
    transaction.rollback()
    connection.close()
    app.dependency_overrides.pop(get_db, None)

@pytest.fixture(scope="function")
def mongo_db():
    test_mongo_db = mongodb_client["crm_test"]
    
    def override_get_mongodb():
        try:
            yield test_mongo_db
        finally:
            pass
            
    app.dependency_overrides[get_mongodb] = override_get_mongodb
    
    yield test_mongo_db
    
    # Clean up test mongo db
    mongodb_client.drop_database("crm_test")
    app.dependency_overrides.pop(get_mongodb, None)

@pytest.fixture(scope="function")
def client(db_session, mongo_db):
    # This TestClient will use the overridden db_session and mongo_db fixtures
    with TestClient(app) as c:
        yield c

@pytest.fixture(scope="function")
def test_user(db_session):
    # Create an isolated user in the test database
    hashed_pwd = get_hashed_password("Secret123!")
    user = User(
        id=999999999,  # Manual BIGINT ID
        full_name="Test User",
        email="testuser@example.com",
        role="Admin",
        password=hashed_pwd
    )
    db_session.add(user)
    db_session.commit()
    return user

@pytest.fixture(scope="function")
def auth_client(client, test_user):
    # Pre-authenticate client with user details
    token = get_jwt_token(
        user_id=test_user.id,
        role=test_user.role,
        full_name=test_user.full_name,
        email=test_user.email
    )
    client.cookies.set("token", token)
    return client
