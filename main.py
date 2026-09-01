import logging
import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 1. Load env vars BEFORE importing modules that rely on them
load_dotenv(override=True)

# Routers
from src.database import Base, engine
from src.routers import account as account_router
from src.routers import account_task as account_task_router
from src.routers import audit_log as audit_log_router
from src.routers import contact as contact_router
from src.routers import project as project_router
from src.routers import project_log as project_log_router
from src.routers import tele_crm as tele_crm_router
from src.routers import user as user_router
from src.routers.authentication import authentication_router
from src.routers.deal_documents import deal_docs_router
from src.routers.deals import deals_router
from src.routers.export_csv import export_csv_router
from src.routers.hiring import candidate_router, jr_router
from src.routers.invoicing_route import invoice_router
from src.routers.notes import notes_router
from src.routers.revenue import revenue_router
from src.routers.support_tickets import support_tickets_router
from src.routers.tickets import tickets_router
from src.routers.webhook import webhook_api_router

# Ensure tables exist
Base.metadata.create_all(bind=engine)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI()

from src.middleware.auth import authorization
from src.middleware.invoice_route_protector import authorize_invoice_route_user

app.middleware("https")(authorize_invoice_route_user)
app.middleware("http")(authorization)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "https://r1xchange-crm.netlify.app",
        "https://r1xchange-crm.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include Routers
app.include_router(account_router.router)
app.include_router(account_task_router.router)
app.include_router(contact_router.router)
app.include_router(user_router.router)
app.include_router(authentication_router)
app.include_router(notes_router)
app.include_router(audit_log_router.router)
app.include_router(project_log_router.router)
app.include_router(deals_router)
app.include_router(export_csv_router)
app.include_router(project_router.router)
app.include_router(tickets_router)
app.include_router(deal_docs_router)
app.include_router(candidate_router)
app.include_router(jr_router)
app.include_router(revenue_router)
app.include_router(webhook_api_router)
app.include_router(support_tickets_router)
app.include_router(invoice_router)
app.include_router(tele_crm_router.router, prefix="/tele-crm")


@app.get("/")
def test():
    return {"message": "Hello World"}


if __name__ == "__main__":
    uvicorn.run(
        app="main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8080)),
        reload=os.getenv("DEV", "false").lower() == "true",
    )

# Tes
