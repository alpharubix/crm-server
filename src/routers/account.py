from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..schemas.account import  AccountCreate, AccountResponse, GetAccountResponse
from ..controllers import account as repo

router = APIRouter(prefix="/accounts", tags=["accounts"])

@router.post("/", response_model=AccountResponse)
def create(data: AccountCreate, db: Session = Depends(get_db)):
    return repo.create_account(db, data)


@router.get("/", response_model=GetAccountResponse)
def list_all(page:int=1,name:str='',phone:str='',company_name:str='',db: Session = Depends(get_db)):
    return repo.get_all_accounts(db,page,name,phone,company_name)

@router.get("/{account_id}", response_model=AccountResponse)
def get_by_id(account_id: int, db: Session = Depends(get_db)):
    return repo.get_account_by_id(db, account_id)

# @router.put("/{account_id}", response_model=AccountResponse)
# def update(account_id: int, data: AccountCreate, db: Session = Depends(get_db)):
#     return repo.update_customer(db, account_id, data)


# @router.post("/{lead_id}/convert")
# def convert_lead(lead_id: int, db: Session = Depends(get_db)):
#     """
#     Transactions:
#     1. Creates Account
#     2. Creates Contact linked to Account
#     3. Marks Lead as 'Converted'
#     """
#     return repo.convert_lead_to_account(db, lead_id)