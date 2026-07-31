import logging
import os
# from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 1. Load env vars BEFORE importing modules that rely on them
load_dotenv(override=True)

# 2. Local imports
# from apscheduler.schedulers.background import BackgroundScheduler

# from src.controllers.Background_threads import BackgroundThreadPool
# from src.database import SessionLocal
# from src.jobs.project_overdue import check_overdue_projects

# Router imports
from src.routers import account as account_router
from src.routers import audit_log as audit_log_router
from src.routers import contact as contact_router
from src.routers import project as project_router
from src.routers import user as user_router
from src.routers.authentication import authentication_router
from src.routers.deal_documents import deal_docs_router
from src.routers.deals import deals_router
from src.routers.export_csv import export_csv_router
from src.routers.hiring import candidate_router, jr_router
from src.routers.notes import notes_router
from src.routers.revenue import revenue_router
from src.routers.tickets import tickets_router
from src.routers.support_tickets import support_tickets_router
from src.routers.webhook import webhook_api_router
from src.routers.invoicing_route import invoice_router
# from src.routers.kotak_hwc_route import kotak_hwc_router
# from src.routers.kotak_ckpl_route import kotak_ckpl_router
# from src.routers.tcpl_route import tcpl_router
# from src.routers.hero_route import hero_router
# from src.routers.muthoot_route import muthoot_router

# 3. Handle setup during the lifespan, not on script execution
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize scheduler globally, but DO NOT start it here
# scheduler = BackgroundScheduler()


# def run_overdue_check():
#     # Session is created inside the job context, which is good
#     db = SessionLocal()
#     try:
#         check_overdue_projects(db)
#     except Exception as e:
#         logger.error(f"Error running overdue check: {e}")
#     finally:
#         db.close()


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # FIX 1: Run blocking/heavy initializations in the background
#     # so FastAPI can finish starting up and pass the Cloud Run health check.
#     import asyncio

#     async def start_background_services():
#         try:
#             # Add a small delay to let Uvicorn bind to the port first
#             await asyncio.sleep(1)

#             logger.info("Initializing Thread Pool...")
#             BackgroundThreadPool.initialize_thread_pool()

#             logger.info("Starting Scheduler...")
#             scheduler.add_job(
#                 run_overdue_check,
#                 trigger="cron",
#                 hour=9,
#                 minute=0,
#                 id="project_overdue_job",
#                 replace_existing=True,
#             )
#             if not scheduler.running:
#                 scheduler.start()
#                 logger.info("Overdue project scheduler started successfully")
#         except Exception as e:
#             logger.error(f"Failed to initialize background services: {e}")

#     # Fire and forget the initialization task so it doesn't block startup
#     asyncio.create_task(start_background_services())

#     yield

#     # Shutdown logic remains the same
#     try:
#         scheduler.shutdown()
#         BackgroundThreadPool.shutdown()
#         logger.info("Scheduler and Thread Pool shutdown complete")
#     except Exception as e:
#         logger.error(f"Error during shutdown: {e}")


# 4. Single App initialization
# app = FastAPI(lifespan=lifespan)
app = FastAPI()

from src.middleware.auth import authorization

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
app.include_router(revenue_router)
app.include_router(webhook_api_router)
app.include_router(support_tickets_router)
app.include_router(invoice_router)
# app.include_router(kotak_hwc_router)
# app.include_router(kotak_ckpl_router)
# app.include_router(tcpl_router)
# app.include_router(hero_router)
# app.include_router(muthoot_router)

@app.get("/")
def test():
    return {"message": "Hello World"}



if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    # FIX 2: Set reload=False for production environments like Cloud Run
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
