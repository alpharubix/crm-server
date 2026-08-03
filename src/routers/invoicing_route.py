from typing import Optional
from fastapi import APIRouter, Depends, File, UploadFile
from starlette.requests import Request
from src.controllers.invoice import (
    get_distributors,
    get_hero_credits,
    get_hero_transactions,
    get_invoices,
    get_kotak_ckpl_credits,
    get_kotak_ckpl_transactions,
    get_kotak_hwc_credits,
    get_kotak_hwc_transactions,
    get_muthoot_credits,
    get_muthoot_transactions,
    get_tcpl_credits,
    get_tcpl_transactions,
    upload_distributor_csv,
    upload_hero_credit_csv,
    upload_hero_transaction_csv,
    upload_invoice_csv,
    upload_kotak_ckpl_credit_csv,
    upload_kotak_ckpl_transaction_csv,
    upload_kotak_hwc_credit_csv,
    upload_kotak_hwc_transaction_csv,
    upload_muthoot_credit_csv,
    upload_muthoot_transaction_csv,
    upload_tcpl_credit_csv,
    upload_tcpl_transaction_csv,
    upload_consolidated_report,
    get_consolidated_limit_report
)

from src.database import get_master_invoice_database

invoice_router = APIRouter(prefix="/invoice")

@invoice_router.post("/upload-distributor-master")
async def upload_distributor_master(request: Request,file: UploadFile = File(...) ,db=Depends(get_master_invoice_database)):
    return await upload_distributor_csv(request,file,db)

@invoice_router.post("/upload-invoice-file")
async def upload_invoice_master(
    request: Request, file: UploadFile = File(...), db=Depends(get_master_invoice_database)
):
    return await upload_invoice_csv(request, file, db)

@invoice_router.post("/kotak-hwc/transaction")
async def upload_kotak_hwc_transaction(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_kotak_hwc_transaction_csv(request,file,db)

@invoice_router.get("/kotak-hwc/transaction")
async def kotak_hwc_transactions(request:Request,
    dealer_name: str | None = None,
    invoice_date: str | None = None,
    invoice_number: str | None = None,
    disbursement_date: str | None = None,
    overdue_within_cure: str | None = None,
    overdue_beyond_cure: str | None = None,
    page=1,db=Depends(get_master_invoice_database)):
    return await get_kotak_hwc_transactions(
        request=request,
        dealer_name=dealer_name,
        invoice_date=invoice_date,
        invoice_number=invoice_number,
        disbursement_date=disbursement_date,
        overdue_within_cure=overdue_within_cure,
        overdue_beyond_cure=overdue_beyond_cure,
        page=page,
        db=db,
    )
@invoice_router.post("/kotak-hwc/credit")
async def upload_kotak_hwc_credit(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_kotak_hwc_credit_csv(request,file,db)

@invoice_router.get("/kotak-hwc/credit")
async def kotak_hwc_credits(
    request: Request,
    dealer_name: str | None = None,
    distributor_code: str | None = None,
    page=1,
    db=Depends(get_master_invoice_database),
):

    return await get_kotak_hwc_credits(
        request=request,
        dealer_name=dealer_name,
        distributor_code=distributor_code,
        page=page,
        db=db,
    )

@invoice_router.post("/kotak-ckpl/transaction")
async def upload_kotak_ckpl_transaction(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_kotak_ckpl_transaction_csv(request,file,db)

@invoice_router.get("/kotak-ckpl/transaction")
async def kotak_ckpl_transactions(
    request: Request,
    dealer_name: str | None = None,
    invoice_date: str | None = None,
    invoice_number: str | None = None,
    disbursement_date: str | None = None,
    overdue_within_cure: str | None = None,
    overdue_beyond_cure: str | None = None,
    page=1,
    db=Depends(get_master_invoice_database),
):

    return await get_kotak_ckpl_transactions(
        request=request,
        dealer_name=dealer_name,
        invoice_date=invoice_date,
        invoice_number=invoice_number,
        disbursement_date=disbursement_date,
        overdue_within_cure=overdue_within_cure,
        overdue_beyond_cure=overdue_beyond_cure,
        page=page,
        db=db,
    )

@invoice_router.post("/kotak-ckpl/credit")
async def upload_kotak_ckpl_credit(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_kotak_ckpl_credit_csv(request,file,db)

@invoice_router.get("/kotak-ckpl/credit")
async def kotak_ckpl_credits(
    request: Request,
    dealer_name: str | None = None,
    distributor_code: str | None = None,
    page=1,
    db=Depends(get_master_invoice_database),
):

    return await get_kotak_ckpl_credits(
        request=request,
        dealer_name=dealer_name,
        distributor_code=distributor_code,
        page=page,
        db=db,
    )

@invoice_router.post("/tcpl/transaction")
async def upload_tcpl_transaction(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_tcpl_transaction_csv(request,file,db)

@invoice_router.get("/tcpl/transaction")
async def tcpl_transactions(
    request: Request,
    customer_name: str | None = None,
    invoice_no: str | None = None,
    invoice_date: str | None = None,
    dpd: str | None = None,
    page=1,
    db=Depends(get_master_invoice_database),
):
    customer_name = customer_name or request.query_params.get("Customer Name")
    invoice_no = invoice_no or request.query_params.get("Invoice No")
    invoice_date = invoice_date or request.query_params.get("Invoice Date")
    dpd = dpd or request.query_params.get("DPD")

    return await get_tcpl_transactions(
        request=request,
        customer_name=customer_name,
        invoice_no=invoice_no,
        invoice_date=invoice_date,
        dpd=dpd,
        page=page,
        db=db,
    )

@invoice_router.post("/tcpl/credit")
async def upload_tcpl_credit(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    print("Route hit")
    return await upload_tcpl_credit_csv(request,file,db)

@invoice_router.get("/tcpl/credit")
async def tcpl_credits(
    request: Request,
    dealer_name: str | None = None,
    distributor_code: str | None = None,
    page=1,
    db=Depends(get_master_invoice_database),
):
    dealer_name = dealer_name or request.query_params.get("Dealer Name")
    distributor_code = distributor_code or request.query_params.get("Distributor Code")

    return await get_tcpl_credits(
        request=request,
        dealer_name=dealer_name,
        distributor_code=distributor_code,
        page=page,
        db=db,
    )

@invoice_router.post("/hero/transaction")
async def upload_hero_transaction(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_hero_transaction_csv(request,file,db)

@invoice_router.get("/hero/transaction")
async def hero_transactions(
    request: Request,
    client_name: str | None = None,
    invoice_number: str | None = None,
    invoice_date: str | None = None,
    dpd: str | None = None,
    page=1,
    db=Depends(get_master_invoice_database),
):
    client_name = client_name or request.query_params.get("Client Name")
    invoice_number = invoice_number or request.query_params.get("Invoice Number")
    invoice_date = invoice_date or request.query_params.get("Invoice Date")
    dpd = dpd or request.query_params.get("DPD")

    return await get_hero_transactions(
        request=request,
        client_name=client_name,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        dpd=dpd,
        page=page,
        db=db,
    )

@invoice_router.post("/hero/credit")
async def upload_hero_credit(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_hero_credit_csv(request,file,db)

@invoice_router.get("/hero/credit")
async def hero_credits(
    request: Request,
    customer_name: str | None = None,
    distributor_code: str | None = None,
    page=1,
    db=Depends(get_master_invoice_database),
):
    customer_name = customer_name or request.query_params.get("Customer Name")
    distributor_code = distributor_code or request.query_params.get("Distributor Code")

    return await get_hero_credits(
        request=request,
        customer_name=customer_name,
        distributor_code=distributor_code,
        page=page,
        db=db,
    )

@invoice_router.post("/muthoot/transaction")
async def upload_muthoot_transaction(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_muthoot_transaction_csv(request,file,db)

@invoice_router.get("/muthoot/transaction")
async def muthoot_transactions(
    request: Request,
    borrower_name: str | None = None,
    invoice_number: str | None = None,
    invoice_date: str | None = None,
    principal_dpd: str | None = None,
    page=1,
    db=Depends(get_master_invoice_database),
):
    return await get_muthoot_transactions(
        request=request,
        borrower_name=borrower_name,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        principal_dpd=principal_dpd,
        page=page,
        db=db,
    )

@invoice_router.post("/muthoot/credit")
async def upload_muthoot_credit(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    print("Route hit")
    return await upload_muthoot_credit_csv(request,file,db)

@invoice_router.get("/muthoot/credit")
async def muthoot_credits(
    request: Request,
    borrower_name: str | None = None,
    distributor_code: str | None = None,
    page=1,
    db=Depends(get_master_invoice_database),
):
    return await get_muthoot_credits(
        request=request,
        borrower_name=borrower_name,
        distributor_code=distributor_code,
        page=page,
        db=db,
    )

@invoice_router.post("/consolidated-limit-report")
async def consolidated_limit(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_consolidated_report(request=request,file=file,db=db)

@invoice_router.get("/consolidated-limit-report")
async def consolidated_limit(request:Request,company_name:str=None,distributor_code:str=None,state:str=None,lender:str=None,
 anchor_id:str=None,billing_status:str=None,page=1,db=Depends(get_master_invoice_database)):
    return await get_consolidated_limit_report(
        request=request,
        company_name=company_name,
        distributor_code=distributor_code,
        state=state,
        lender=lender,
        anchor_id=anchor_id,
        billing_status=billing_status,
        page=page,
        db=db,
    )

@invoice_router.get("/distributors")
async def distributors(request:Request,page=1,anchor: str = None,
    region: str = None,
    state: str = None,
    distribution_type: str = None,
    division: str = None,db=Depends(get_master_invoice_database)):
    return await get_distributors(request=request,anchor=anchor,
    region = region,
    state = state,
    distribution_type = distribution_type,
    division = division,page=page,db=db)

@invoice_router.get("/")
async def invoices(
    request: Request,
    page: int = 1,
    limit: int = 10,
    anchor: Optional[str] = None,
    processed_by: Optional[str] = None,
    working_date: Optional[str] = None,
    lender_name: Optional[str] = None,
    distributor_name: Optional[str] = None,
    distributor_code: Optional[str] = None,
    invoice_no: Optional[str] = None,
    loan_disbursement_date: Optional[str] = None,
    utr: Optional[str] = None,
    status: Optional[str] = None,
    status_reason: Optional[str] = None,
    db=Depends(get_master_invoice_database),
):
    return await get_invoices(
        request=request,
        db=db,
        anchor=anchor,
        processed_by=processed_by,
        working_date=working_date,
        lender_name=lender_name,
        distributor_name=distributor_name,
        distributor_code=distributor_code,
        invoice_no=invoice_no,
        loan_disbursement_date=loan_disbursement_date,
        utr=utr,
        status=status,
        status_reason=status_reason,
        page=page,
        limit=limit,
    )

@invoice_router.get("/check-health")
async def get_health():
    return {"status": "working"}

#update history routes
