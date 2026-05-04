from contextlib import asynccontextmanager

from fastapi.middleware.cors import CORSMiddleware
from src.database import Base, engine
from src.middleware.auth import authorization
from src.models.audit_log import AuditLog  # so Base picks it up
from src.models.contact import Contact
from src.models.project import Project, Task
from src.routers import account as account_router
from src.routers import audit_log as audit_log_router
from src.routers import contact as contact_router
from src.routers import user as user_router
from src.routers import project as project_router
from src.routers.authentication import authentication_router
from src.routers.notes import notes_router
from src.routers.deals import deals_router
from src.routers.tickets import tickets_router
from src.routers.export_csv import export_csv_router
from src.routers.deal_documents import deal_docs_router
from src.routers.hiring import candidate_router, jr_router
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from src.controllers.Background_threads import BackgroundThreadPool
load_dotenv(override=True)

'''
Long Server Start Cause:
These functions runs synchronously at the module level. It queries the database over the network to fetch the schema for every existing table. This causes severe blocking I/O during initialization.

Do not reflect or create tables on application startup. Use alembic (which is already in dependencies) to manage database migrations offline.
'''
# Base.metadata.clear()
# Base.metadata.reflect(bind=engine)
# Base.metadata.create_all(bind=engine)

app = FastAPI()


@asynccontextmanager
async def lifespan(app: FastAPI):
    BackgroundThreadPool.initialize_thread_pool()
    yield
    BackgroundThreadPool.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/")
def test():
    return {"message": "Hello World"}

app.middleware("http")(authorization)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "https://r1xchange-crm.netlify.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account_router.router)
app.include_router(contact_router.router)
app.include_router(user_router.router)
app.include_router(authentication_router)
app.include_router(notes_router)
app.include_router(audit_log_router.router)
app.include_router(deals_router)
app.include_router(export_csv_router)
app.include_router(project_router.router)
app.include_router(tickets_router)
app.include_router(deal_docs_router)
app.include_router(candidate_router)
app.include_router(jr_router)

if __name__ == "__main__":
    # Cloud Run provides PORT as an env var; default to 8080 if not found
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
