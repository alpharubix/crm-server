from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.params import Body
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from starlette.requests import Request
from ..controllers.account import update_account as update_account_controller
from ..controllers import account as repo
from ..controllers.audit_log import log_action
from ..database import get_db, get_mongodb
from ..models.account import Account
from ..schemas.account import AccountBase, GetlistAccountResponse, ListAccountsResponse, AccountStatusHistoryResponse

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("/")
@router.post("")
def create(request: Request, data: AccountBase, db: Session = Depends(get_db)):
    user_id = int(request.state.user_id)
    user_role = request.state.role
    account = repo.create_account(db, data, user_id=user_id, user_role=user_role)
    return {"id": account.id, "message": "Account created successfully"}


@router.get("/", response_model=GetlistAccountResponse,response_model_exclude_none=True)
@router.get("", response_model=GetlistAccountResponse,response_model_exclude_none=True)
def list_all(
    request: Request,
    account_id: int | None = None,
    city: str | None = None,
    page: int = 1,
    state: str | None = None,
    db: Session = Depends(get_db),
    mongodb=Depends(get_mongodb),
    account_stage: str | None = None,
    account_status: str | None = None,
    account_name: Optional[str] = None,
    account_owner_id: Optional[int] = None,
    industry: str | None = None,
    source: Optional[str] = None,
    phone: str | None = None,
    call_back_date_time: str = None,
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
        account_name=account_name,
        account_owner_id=account_owner_id,
        source=source,
        phone_number=phone,
        industry=industry,
        call_back_date_time=call_back_date_time,
        # map others only if they exist in repo
    )


@router.put("/{account_id}")
async def update_account(
    request: Request,
    account_id: int,
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
):
    user_id = int(request.state.user_id)
    user_role = request.state.role
    updated = update_account_controller(db, account_id, payload, user_id, user_role)
    return {"message": "update-success", "updated_account": updated}


#account status trackin route
@router.get("/status-history/{account_id}", response_model=list[AccountStatusHistoryResponse])
def get_status_history(
    account_id: int,
    page: int = 1,
    db: Session = Depends(get_db)
):
    return repo.get_account_status_history(db, account_id, page)


@router.post("/accounts-reassignment-csv-upload")
async def upload_accounts_csv(
    file: UploadFile = File(...), db: Session = Depends(get_db)
):
    # check if the file is in csv format or not
    print("file is under processing")
    response = await repo.accounts_csv_update(file, db)
    return response


@router.get("/lookup", response_model=ListAccountsResponse)
def get_accounts_ids(account_name: str, db: Session = Depends(get_db)):
    return repo.fetch_account_id(account_name, db)


@router.post("/accounts-update-csv-upload")
async def accounts_update_csv(
    request: Request, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    try:
        user_id = request.state.user_id
        return await repo.update_accounts_based_on_csv(file, db, user_id)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"unable to process csv error: {str(e)}"
        )


# @router.post("/accounts-update-csv-upload")
# async def accounts_update_csv(file:UploadFile=File(...), db: Session = Depends(get_db)):
#     await repo.update_accounts_based_on_csv(file, db)
#     return {"message":"file upload success"}
