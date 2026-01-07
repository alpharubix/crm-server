from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.params import Body
from sqlalchemy.orm import Session
from starlette.requests import Request

from ..controllers import account as repo
from ..database import get_db, get_mongodb
from ..models.account import Account
from ..schemas.account import AccountBase, GetlistAccountResponse

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("/")
@router.post("")
def create(data: AccountBase, db: Session = Depends(get_db)):
    return repo.create_account(db, data)


@router.get("/", response_model=GetlistAccountResponse)
@router.get("", response_model=GetlistAccountResponse)
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
        # map others only if they exist in repo
    )


@router.put("{account_id}")
@router.put("/{account_id}")
async def update_account(
    account_id: int,
    payload: Dict[str, Any] = Body(...),  # Takes the raw JSON as a dict
    db: Session = Depends(get_db),
):
    # 1. Locate the record in PostgreSQL
    db_account = db.query(Account).filter(Account.id == account_id).first()

    if not db_account:
        raise HTTPException(status_code=404, detail=({"msg": "Account not found"}))

    # 2. Iterate and Update
    # This dynamically sets attributes on your SQLAlchemy model
    for key, value in payload.items():
        if hasattr(db_account, key):
            # Special handling for datetime strings if they come as strings
            if "time" in key or "date" in key:
                if isinstance(value, str):
                    try:
                        value = datetime.fromisoformat(value)
                    except ValueError:
                        pass  # Or handle specific date formatting errors

            setattr(db_account, key, value)

    # 3. Save changes
    try:
        db.commit()
        db.refresh(db_account)
        return {"message": "update-success", "updated_account": db_account}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")
