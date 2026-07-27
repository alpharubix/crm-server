from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
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
from ..config import settings
import httpx

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("/")
@router.post("")
def create(request: Request, data: AccountBase, db: Session = Depends(get_db)):
    user_id = int(request.state.user_id)
    user_role = request.state.role
    account = repo.create_account(db, data, user_id=user_id, user_role=user_role)
    return {"id": account.id, "message": "Account created successfully"}


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
    account_status: list[str] | None = Query(default=None),
    account_name: Optional[str] = None,
    account_owner_id: list[int] | None = Query(default=None),
    industry: list[str] | None = Query(default=None),
    source: list[str] | None = Query(default=None),
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
    user_role = request.state.role
    if user_role not in ("super_admin", "admin", "manager"):
        raise HTTPException(
            status_code=403, detail="You do not have permission to upload CSV"
        )
    try:
        user_id = request.state.user_id
        return await repo.update_accounts_based_on_csv(file, db, user_id, user_role)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"unable to process csv error: {str(e)}"
        )


# @router.post("/accounts-update-csv-upload")
# async def accounts_update_csv(file:UploadFile=File(...), db: Session = Depends(get_db)):
#     await repo.update_accounts_based_on_csv(file, db)
#     return {"message":"file upload success"}

@router.get("/r1xcrm-summary-of-debit-and-credit_monthwise/{acc_id}")
async def get_r1xcrm_summary_of_debit_and_credit_monthwise(
    request: Request,
    acc_id: int,
):
    try:
        print("hii")
        url = (
            f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}"
            f"/bsa/r1xcrm-summary-of-debit-and-credit_monthwise/{acc_id}"
        )
        print(url)

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                url,
                params=request.query_params,
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.json()
            )

        return response.json()

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Unable to connect to 5PointCredit: {e}"
        )

@router.get("/r1xcrm-cashflow/{acc_id}")
async def get_r1xcrm_cashflow(
    request: Request,
    acc_id: int,
):
    try:
        url = (
            f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}"
            f"/bsa/r1xcrm-cashflow/{acc_id}"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=request.query_params)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Unable to connect to 5PointCredit: {e}")

@router.get("/r1xcrm-month-wise-overview/{acc_id}")
async def get_r1xcrm_month_wise_overview(
    request: Request,
    acc_id: int,
):
    try:
        url = (
            f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}"
            f"/bsa/r1xcrm-month-wise-overview/{acc_id}"
        )
        # Handle param mapping if needed
        params = dict(request.query_params)
        if "from_month" in params:
            params["from_date"] = params.pop("from_month")
        if "to_month" in params:
            params["to_date"] = params.pop("to_month")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=params)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Unable to connect to 5PointCredit: {e}")

@router.get("/r1xcrm-report-date-range/{acc_id}")
async def get_r1xcrm_report_date_range(
    request: Request,
    acc_id: int,
):
    try:
        url = (
            f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}"
            f"/bsa/r1xcrm-report-date-range/{acc_id}"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, params=request.query_params)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Unable to connect to 5PointCredit: {e}")


# routers for tax calculation
@router.get("/r1xcrm-tax-calculation/{acc_id}")
async def get_r1xcrm_tax_calculation(
    request: Request,
    acc_id: int,
):
    try:
        url = (
            f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}"
            f"/itr/r1xcrm-tax-calculation/{acc_id}"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Unable to connect to 5PointCredit: {e}")

@router.get("/r1xcrm-balance_sheet/{acc_id}")
async def get_r1xcrm_balance_sheet(
    request: Request,
    acc_id: int,
):
    try:
        url = (
            f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}"
            f"/itr/r1xcrm-balance_sheet/{acc_id}"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Unable to connect to 5PointCredit: {e}")

@router.get("/r1xcrm-profit-and-loss-statement/{acc_id}")
async def get_r1xcrm_profit_and_loss_statement(
    request: Request,
    acc_id: int,
):
    try:
        url = (
            f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}"
            f"/itr/r1xcrm-profit-and-loss-statement/{acc_id}"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Unable to connect to 5PointCredit: {e}")

@router.get("/r1xcrm-ratio-analysis/{acc_id}")
async def get_r1xcrm_ratio_analysis(
    request: Request,
    acc_id: int,
):
    try:
        url = (
            f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}"
            f"/itr/r1xcrm-ratio-analysis/{acc_id}"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Unable to connect to 5PointCredit: {e}")

# rouers for gst

@router.get("/r1xcrm-gst-basic-info/{acc_id}")
async def get_r1xcrm_gst_basic_info(
    request: Request,
    acc_id: int,
):
    try:
        url = (
            f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}"
            f"/gst/r1xcrm-gst-ref-status/{acc_id}"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Unable to connect to 5PointCredit: {e}")


@router.post("/r1xcrm-overview")
async def get_r1xcrm_overview(
    request: Request,
):
    try:
        url = (
            f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}"
            f"/gst/r1xcrm-overview"
        )
        body = await request.json()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url,json=body)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Unable to connect to 5PointCredit: {e}")



@router.post("/r1xcrm-top-suppliers-and-customers")
async def get_r1xcrm_top_suppliers_and_customers(
    request: Request,
):
    try:
        url = (
            f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}"
            f"/gst/r1xcrm-top-suppliers-and-customers"
        )
        body = await request.json()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url,json=body)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Unable to connect to 5PointCredit: {e}")


@router.post("/r1xcrm-monthly-sales-purchase-summary")
async def get_r1xcrm_monthly_sales_purchase_summary(
    request: Request,
):
    try:
        url = (
            f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}"
            f"/gst/r1xcrm-monthly-sales-purchase-summary"
        )
        body = await request.json()
        print(body)
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url,json=body)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Unable to connect to 5PointCredit: {e}")


@router.get("/check-r1xchange-account/{acc_id}")
async def check_r1xchange_account(
    request: Request,
    acc_id: int,
):
    try:
        url = (
            f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}"
            f"/auth/check-r1xchange-account/{acc_id}"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Unable to connect to 5PointCredit: {e}")

@router.get("/r1xcrm-list-reports/{acc_id}")
async def r1xcrm_list_reports(
    request: Request,
    acc_id: int,
):
    try:
        url = ( 
            f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}"
            f"/cibil/r1xcrm-list-reports/{acc_id}"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Unable to connect to 5PointCredit: {e}")



@router.get("/r1xcrm-overview/{reference_id}")
async def get_cibil_r1xcrm_overview(
    request: Request,
    reference_id: str,
):
    try:
        url = (
            f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}"
            f"/cibil/r1xcrm-overview/{reference_id}"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Unable to connect to 5PointCredit: {e}")



@router.get("/r1xcrm-account-summary/{reference_id}")
async def get_r1xcrm_account_summary(
    request: Request,
    reference_id: str,
):
    try:
        url = (
            f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}"
            f"/cibil/r1xcrm-account-summary/{reference_id}"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Unable to connect to 5PointCredit: {e}")


@router.get("/r1xcrm-payment-history/{reference_id}")
async def get_r1xcrm_payment_history(
    request: Request,
    reference_id: str,
):
    try:
        url = (
            f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}"
            f"/cibil/r1xcrm-payment-history/{reference_id}"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Unable to connect to 5PointCredit: {e}")


@router.get("/r1xcrm-analysis/{reference_id}")
async def get_r1xcrm_analysis(
    request: Request,
    reference_id: str,
):
    try:
        url = (
            f"{settings.FIVE_POINT_CREDIT_BACKEND_URL}"
            f"/cibil/r1xcrm-analysis/{reference_id}"
        )
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.json())
        return response.json()
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Unable to connect to 5PointCredit: {e}")

