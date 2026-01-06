from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.requests import Request
from ..database import get_db,get_mongodb
from ..schemas.account import  GetlistAccountResponse,AccountBase
from ..controllers import account as repo

router = APIRouter(prefix="/accounts", tags=["accounts"])

@router.post("/")
def create(data: AccountBase, db: Session = Depends(get_db)):
    return repo.create_account(db, data)


@router.get("/",response_model=GetlistAccountResponse)
def list_all(
    request: Request,
    account_id: int | None = None,
    city: str | None = None,
    page: int = 1,
    state: str | None = None,
    db: Session = Depends(get_db),
    mongodb = Depends(get_mongodb),
    account_stage:str|None = None,
    account_status:str|None = None,
    account_name:Optional[str] = None
):
    return repo.get_all_accounts(
        request=request,
        db=db,
        mongodb=mongodb,
        page=page,
        account_id=account_id,
        city=city,
        state=state,
        account_stage=account_stage,
        account_status=account_status,
        account_name=account_name
        # map others only if they exist in repo
    )
