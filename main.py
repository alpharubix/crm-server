import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv

# 1. Load env vars BEFORE importing modules that rely on them
load_dotenv(override=True)

# 2. Local imports
from src.database import Base, engine
from src.middleware.auth import authorization
from src.controllers.Background_threads import BackgroundThreadPool

# Router imports
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
from src.routers.revenue import revenue_router

# 3. Handle setup during the lifespan, not on script execution
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables only when the app is actively starting up
    # Base.metadata.create_all(bind=engine)
    BackgroundThreadPool.initialize_thread_pool()
    yield
    BackgroundThreadPool.shutdown()

# 4. Single App initialization
app = FastAPI(lifespan=lifespan)

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

@app.get("/")
def test():
    return {"message": "Hello World"}

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    # Turn reload=False if you want to isolate environment/network start speeds
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)