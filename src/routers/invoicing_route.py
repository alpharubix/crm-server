from fastapi import APIRouter, Depends, File, UploadFile
from starlette.requests import Request
from src.controllers.invoice import upload_distributor_csv,upload_invoice_csv,upload_kotak_hwc_transaction_csv,upload_kotak_ckpl_credit_csv,upload_kotak_ckpl_transaction_csv,upload_kotak_hwc_credit_csv,upload_muthoot_credit_csv,upload_muthoot_transaction_csv,upload_tcpl_credit_csv,upload_tcpl_transaction_csv,get_invoices,get_distributors

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

@invoice_router.post("/kotak-hwc/credit")
async def upload_kotak_hwc_credit(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_kotak_hwc_credit_csv(request,file,db)

@invoice_router.post("/kotak-ckpl/transaction")
async def upload_kotak_ckpl_transaction(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_kotak_ckpl_transaction_csv(request,file,db)

@invoice_router.post("/kotak-ckpl/credit")
async def upload_kotak_ckpl_credit(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_kotak_ckpl_credit_csv(request,file,db)

@invoice_router.post("/tcpl/transaction")
async def upload_tcpl_transaction(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    return await upload_tcpl_transaction_csv(request,file,db)

@invoice_router.post("/tcpl/credit")
async def upload_tcpl_credit(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    print("Route hit")
    return await upload_tcpl_credit_csv(request,file,db)

@invoice_router.post("/muthoot/transaction")
async def upload_muthoot_transaction(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    print("Route hit")
    return await upload_muthoot_transaction_csv(request,file,db)

@invoice_router.post("/muthoot/credit")
async def upload_muthoot_credit(request:Request,file:UploadFile=File(...),db=Depends(get_master_invoice_database)):
    print("Route hit")
    return await upload_muthoot_credit_csv(request,file,db)

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





