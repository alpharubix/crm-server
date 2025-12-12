import uvicorn
from fastapi import FastAPI
from src.database import engine
from src.models.lead import Base as LeadBase
from src.routers import lead
from fastapi.middleware.cors import CORSMiddleware

LeadBase.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows ALL origins (React, Postman, etc.) - Perfect for Dev
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, PUT, DELETE)
    allow_headers=["*"],  # Allows all headers (Authorization, Content-Type)
)

app.include_router(lead.router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="localhost", port=8080, reload=True)

