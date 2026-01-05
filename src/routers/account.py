
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.requests import Request
from ..database import get_db,get_mongodb
from ..schemas.account import  GetlistAccountResponse,AccountBase
from ..controllers import account as repo

router = APIRouter(prefix="/accounts", tags=["accounts"])

@router.post("/",)
def create(data: AccountBase, db: Session = Depends(get_db)):
    return repo.create_account(db, data)


@router.get("/",response_model=GetlistAccountResponse)
def list_all(request:Request,account_id:int=None,page:int=1,phone:str='',company_name:str='',db: Session = Depends(get_db),mongodb = Depends(get_mongodb)):
    return repo.get_all_accounts(request,db,mongodb,page,account_id,phone,company_name)