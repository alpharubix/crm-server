from fastapi import APIRouter, Depends, File, UploadFile
from starlette.requests import Request

from src.controllers.invoice import upload_invoice_file
from src.database import get_mongodb


invoice_router = APIRouter(prefix="/invoice")


@invoice_router.post("/upload-invoice-file")
async def upload_invoice(
    request: Request, file: UploadFile = File(...), db=Depends(get_mongodb)
):
    return await upload_invoice_file(request, file, db)


@invoice_router.get("/check-health")
async def get_health():
    return {"status": "working"}
