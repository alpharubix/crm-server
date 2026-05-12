from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.requests import Request
from starlette import status
from src.controllers.revenue import insert_revenue,fetch_revenue,update_revenue_controller
from src.database import get_db
from src.schemas.revenue import Revenue,RevenueUpdateSchema

revenue_router = APIRouter(prefix="/revenue", tags=["revenue"])

@revenue_router.post('')
async def creat_revenue(request:Request,body:Revenue,pg_db_session: Session = Depends(get_db)):
   try:
       user_id = request.state.user_id
       role = request.state.role
       return insert_revenue(user_id=user_id,user_role=role,data=vars(body),db=pg_db_session)
   except HTTPException as e:
       raise e
@revenue_router.get("")
async def get_revenue(
    request: Request,
    pg_db_session: Session = Depends(get_db),

    # pagination
    page: int = 1,

    # filters
    revenue_id: str | None = None,
    account_name: str = "",
    lender_name: str = "",
    reference_number: str = "",
    income_booking_date: str = "",
    type_of_revenue: str = "",
    amount: str = "",
    gst_amount: str = "",
):
    try:

        return fetch_revenue(
            request=request,
            db=pg_db_session,
            page=page,
            revenue_id=int(revenue_id) if revenue_id else None,
            account_name=account_name,
            lender_name=lender_name,
            reference_number=reference_number,
            income_booking_date=income_booking_date,
            type_of_revenue=type_of_revenue,
            amount=amount,
            gst_amount=gst_amount,
        )

    except HTTPException as e:
        raise e

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )

@revenue_router.patch("/{revenue_id}")
def update_revenue_route(
    request: Request,
    revenue_id: int,
    data: RevenueUpdateSchema,
    db: Session = Depends(get_db)
):
    try:
        user_id = request.state.user_id
        role = request.state.role
        return update_revenue_controller(
            revenue_id=revenue_id,
            data=data,
            user_id=user_id,
            role=role,
            db=db
        )
    except HTTPException as e:
        raise e