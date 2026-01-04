from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas.authentication import Login
from ..controllers.auth import validate_login
authentication_router = APIRouter(prefix="/login", tags=["authentication"])


@authentication_router.post("/")
def login(body:Login,db: Session = Depends(get_db)):
    return validate_login(body,db)
