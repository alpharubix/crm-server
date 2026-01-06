import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.database import Base, engine
from src.middleware.auth import authorization
from src.routers import account as account_router
from src.routers import contact as contact_router
from src.routers import user as user_router
from src.routers.authentication import authentication_router
from src.routers.notes import notes_router

Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.get("/")
def test():
    return {"message": "Hello World"}


app.middleware("http")(authorization)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174","https://r1xchange-crm.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account_router.router)
app.include_router(contact_router.router)
app.include_router(user_router.router)
app.include_router(authentication_router)
app.include_router(notes_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="localhost", port=8080, reload=True)
