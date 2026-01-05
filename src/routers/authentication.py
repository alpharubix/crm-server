from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import Response
from ..database import get_db
from ..schemas.authentication import Login
from ..controllers.auth import validate_login
from ..controllers.user import get_me
authentication_router = APIRouter(prefix="/auth", tags=["authentication"])


@authentication_router.post("/login")
def login(body:Login,db: Session = Depends(get_db)):
    return validate_login(body,db)


@authentication_router.post("/logout")
def logout(response: Response):
    response.delete_cookie(
        key="token",
        httponly=True,
        secure=True,  # must match how it was set
    )
    return {"message": "Logout successful"}

@authentication_router.get("/get-me")
def get_user(request:Request,db: Session = Depends(get_db)):
    return get_me(request,db)

