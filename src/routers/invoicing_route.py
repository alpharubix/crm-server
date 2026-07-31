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
async def kotak_hwc_transactions(request:Request,page=1,db=Depends(get_master_invoice_database)):
    return await get_kotak_hwc_transactions(request=request,page=page,db=db)

@invoice_router.post("/kotak-hwc/credit")
async def upload_kotak_hwc_credit(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_kotak_hwc_credit_csv(request,file,db)

@invoice_router.get("/kotak-hwc/credit")
async def kotak_hwc_credits(request:Request,page=1,db=Depends(get_master_invoice_database)):
    return await get_kotak_hwc_credits(request=request,page=page,db=db)

@invoice_router.post("/kotak-ckpl/transaction")
async def upload_kotak_ckpl_transaction(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_kotak_ckpl_transaction_csv(request,file,db)

@invoice_router.get("/kotak-ckpl/transaction")
async def kotak_ckpl_transactions(request:Request,page=1,db=Depends(get_master_invoice_database)):
    return await get_kotak_ckpl_transactions(request=request,page=page,db=db)

@invoice_router.post("/kotak-ckpl/credit")
async def upload_kotak_ckpl_credit(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_kotak_ckpl_credit_csv(request,file,db)

@invoice_router.get("/kotak-ckpl/credit")
async def kotak_ckpl_credits(request:Request,page=1,db=Depends(get_master_invoice_database)):
    return await get_kotak_ckpl_credits(request=request,page=page,db=db)

@invoice_router.post("/tcpl/transaction")
async def upload_tcpl_transaction(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_tcpl_transaction_csv(request,file,db)

@invoice_router.get("/tcpl/transaction")
async def tcpl_transactions(request:Request,page=1,db=Depends(get_master_invoice_database)):
    return await get_tcpl_transactions(request=request,page=page,db=db)

@invoice_router.post("/tcpl/credit")
async def upload_tcpl_credit(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    print("Route hit")
    return await upload_tcpl_credit_csv(request,file,db)

@invoice_router.get("/tcpl/credit")
async def tcpl_credits(request:Request,page=1,db=Depends(get_master_invoice_database)):
    return await get_tcpl_credits(request=request,page=page,db=db)

@invoice_router.post("/hero/transaction")
async def upload_hero_transaction(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_hero_transaction_csv(request,file,db)

@invoice_router.get("/hero/transaction")
async def hero_transactions(request:Request,page=1,db=Depends(get_master_invoice_database)):
    return await get_hero_transactions(request=request,page=page,db=db)

@invoice_router.post("/hero/credit")
async def upload_hero_credit(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_hero_credit_csv(request,file,db)

@invoice_router.get("/hero/credit")
async def hero_credits(request:Request,page=1,db=Depends(get_master_invoice_database)):
    return await get_hero_credits(request=request,page=page,db=db)

@invoice_router.post("/muthoot/transaction")
async def upload_muthoot_transaction(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    print("Route hit")
    return await upload_muthoot_transaction_csv(request,file,db)

@invoice_router.get("/muthoot/transaction")
async def muthoot_transactions(request:Request,page=1,db=Depends(get_master_invoice_database)):
    return await get_muthoot_transactions(request=request,page=page,db=db)

@invoice_router.post("/muthoot/credit")
async def upload_muthoot_credit(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    print("Route hit")
    return await upload_muthoot_credit_csv(request,file,db)

@invoice_router.get("/muthoot/credit")
async def muthoot_credits(request:Request,page=1,db=Depends(get_master_invoice_database)):
    return await get_muthoot_credits(request=request,page=page,db=db)



@invoice_router.get("/distributors")
async def distributors(request:Request,page=1,db=Depends(get_master_invoice_database)):
    return await get_distributors(request=request,page=page,db=db)

@invoice_router.get("/")
async def invoices(request:Request,page=1,db=Depends(get_master_invoice_database)):

    return await get_invoices(request=request,page=page,db=db)

@invoice_router.get("/check-health")
async def get_health():
    return {"status": "working"}

#update history routes





