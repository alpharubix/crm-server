from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import HTTPException
from sqlalchemy.orm import Session

from ..controllers.user import insert_already_existing_user,get_user_filter
from ..database import get_db
from ..models.user import User
from ..schemas.user import ExistingUser, UserFilterResponse

router = APIRouter(prefix="/user")


@router.post("/create-user")
async def create_user(user: ExistingUser, db: Session = Depends(get_db)):
    return insert_already_existing_user(user, db)


@router.get("/filter", response_model=UserFilterResponse)
async def get_user(request: Request, db: Session = Depends(get_db)):
   return get_user_filter(request,db)


@router.get("")
async def get_all_users(db: Session = Depends(get_db)):
    return db.query(User.id, User.full_name, User.email, User.role).all()
