from fastapi import APIRouter,UploadFile,File,Depends
from starlette.requests import Request
from starlette import status as status
from src.database import get_mongodb
from src.controllers.distributor import upload_file
distributor_router = APIRouter(prefix="/dist")


@distributor_router.post("/upload-dist-file")
async def upload_dist(request:Request,file:UploadFile=File(...),db=Depends(get_mongodb)):
    return await upload_file(request,file,db)



@distributor_router.get("/check-health")
async def get_health():
    return {
        "status":"working"
    }