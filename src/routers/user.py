from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..schemas.user import ExistingUser
from ..controllers.user import insert_already_existing_user
from ..database import get_db
from ..models.user import User
router = APIRouter(prefix="/user", tags=["users"])


@router.post("/create-user")
async def create_user(user: ExistingUser,db: Session = Depends(get_db)):
    return insert_already_existing_user(user,db)

@router.get("/")
async def get_user(db: Session = Depends(get_db)):
    return db.query(User).all()