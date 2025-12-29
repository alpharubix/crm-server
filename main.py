import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.database import Base, engine
from src.models import account, contact  # type: ignore
from src.routers import account as account_router
from src.routers import contact as contact_router

app = FastAPI()


Base.metadata.create_all(bind=engine)


@app.get("/")
def test():
    return {"message": "Hello World"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account_router.router)
app.include_router(contact_router.router)
if __name__ == "__main__":
    uvicorn.run("main:app", host="localhost", port=8080, reload=True)
