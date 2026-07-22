import json
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse
from src.controllers.account import update_account
from src.database import get_db
logging.basicConfig(level=logging.INFO)
webhook_api_router = APIRouter(prefix="/webhook", tags=["webhook"])



@webhook_api_router.patch("/update-account-name/{account_id}", tags=["webhook"])
async def update_account_name(request: Request,account_id:str,db: Session = Depends(get_db)):
    try:
        input_data = await request.json()

        if not input_data:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "payload is incorrect"})

        if not input_data["account_name"]:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "account_name is required"})

        user_id = 1
        user_role = "admin"

        update_account(db, int(account_id), input_data,user_id,user_role)

        return JSONResponse(status_code=status.HTTP_200_OK, content={"message": "Account name updated"})

    except json.JSONDecodeError as e:
        logging.error(e)
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": "invalid json"})

    except Exception as e:
        logging.error(e)
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"message": str(e)})















