import math
from datetime import datetime, timezone
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, true
from sqlalchemy.orm import Session, selectinload
from starlette import status
from starlette.requests import Request

from src.controllers.audit_log import log_action
from src.models.user import User
from src.controllers.auth import MANAGERID
from src.models.revenue import Revenue

def insert_revenue(user_id, user_role,data, db: Session):
    try:
        revenue = Revenue()

        # assign values dynamically
        for key, value in data.items():
            if hasattr(revenue, key):
                setattr(revenue, key, value)

        # optional: assign created_by / user_id
        revenue.owner_id = int(user_id)
        revenue.created_by = int(user_id)
        revenue.created_at = datetime.now(timezone.utc)

        # add to database
        db.add(revenue)
        db.commit()
        db.refresh(revenue)
        # convert SQLAlchemy object to dict
        updated_revenue = {
            column.name: getattr(revenue, column.name)
            for column in revenue.__table__.columns
        }

        # convert dates/datetime to JSON serializable format
        updated_revenue = jsonable_encoder(updated_revenue)

        # audit log
        log_action(
            db,
            user_id,
            user_role,
            "CREATED",
            "Revenue",
            revenue.id,
            updated_revenue
        )

        return {
            "success": True,
            "message": "Revenue created successfully",
            "data": updated_revenue
        }

    except Exception as e:
        print(e)
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )


def fetch_revenue(
    request,
    db: Session,
    page: int = 1,
    revenue_id: int = None,
    account_name: str = "",
    lender_name: str = "",
    reference_number: str = "",
    income_booking_date: str = "",
    type_of_revenue: str = "",
    amount: float = None,
    gst_amount: float = None,
):
    try:
        MANAGER_EXECUTIVES_MAP = MANAGERID().MANAGER_EXECUTIVES_MAP

        limit = 30
        offset = (page - 1) * limit

        query = db.query(Revenue)
        filters = []

        user_id = request.state.user_id
        role = request.state.role

        allowed_owner_ids = None
        single_id_request = False

        # ---------------- ROLE BASED ACCESS ---------------- #

        if role in ("super_admin", "admin"):
            pass

        elif role == "manager":
            allowed_owner_ids = [user_id] + MANAGER_EXECUTIVES_MAP.get(user_id, [])

        elif role == "executive":
            allowed_owner_ids = [user_id]

        if allowed_owner_ids is not None:
            filters.append(Revenue.owner_id.in_(allowed_owner_ids))

        # ---------------- FILTERS ---------------- #

        if revenue_id:
            filters.append(Revenue.id == revenue_id)
            single_id_request = True

        if account_name and account_name.strip():
            filters.append(
                Revenue.account_name.ilike(f"%{account_name.strip()}%")
            )

        if lender_name and lender_name.strip():
            filters.append(
                Revenue.lender_name.ilike(f"%{lender_name.strip()}%")
            )

        if reference_number and reference_number.strip():
            filters.append(
                Revenue.reference_number.ilike(
                    f"%{reference_number.strip()}%"
                )
            )

        if income_booking_date and income_booking_date.strip():
            filters.append(
                Revenue.income_booking_date == income_booking_date.strip()
            )

        if type_of_revenue and type_of_revenue.strip():
            filters.append(
                Revenue.type_of_revenue.ilike(
                    f"%{type_of_revenue.strip()}%"
                )
            )

        if amount and str(amount).strip():
            filters.append(
                Revenue.amount == amount
            )

        if gst_amount and str(gst_amount).strip():
            filters.append(
                Revenue.gst_amount == gst_amount
            )

        # ---------------- SINGLE RECORD FETCH ---------------- #

        if single_id_request:

            base_query = (
                query.filter(and_(*filters))
                if filters
                else query
            )

            total_data_size = base_query.count()

            data = (
                base_query
                .options(
                    selectinload(Revenue.revenue_owner).load_only(User.full_name,User.role),
                    selectinload(Revenue.updater).load_only(User.full_name,User.role),
                    selectinload(Revenue.creator).load_only(User.full_name,User.role),
                )
                .offset(offset)
                .limit(limit)
                .all()
            )

            total_pages = math.ceil(total_data_size / limit)


            return {
                "success": True,
                "message": "Revenue fetched successfully",
                "data": data,
                "page_info": {
                    "page": page,
                    "total_pages": total_pages,
                    "data_size": total_data_size,
                },
            }

        # ---------------- LIGHTWEIGHT FETCH ---------------- #

        else:

            data = (
                db.query(
                    Revenue.id,
                    Revenue.account_name,
                    Revenue.lender_name,
                    Revenue.reference_number,
                    Revenue.income_booking_date,
                    Revenue.type_of_revenue,
                    Revenue.amount,
                    Revenue.gst_amount,
                )
                .filter(and_(*filters))
                .offset(offset)
                .limit(limit)
                .all()
            )

            total_data_size = (
                query.filter(and_(*filters)).count()
            )

            total_pages = math.ceil(total_data_size / limit)

            data = [dict(row._mapping) for row in data]

            return {
                "success": True,
                "message":"Revenue fetched successfully",
                "data": data,
                "page_info": {
                    "page": page,
                    "total_pages": total_pages,
                    "data_size": total_data_size,
                },
            }

    except Exception as e:
        print("Error at fetch_revenue:", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

def update_revenue_controller(
    revenue_id: int,
    data,
    user_id,
    role,
    db: Session
):
    try:

        revenue = (
            db.query(Revenue)
            .filter(Revenue.id == revenue_id)
            .first()
        )

        if not revenue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Revenue not found"
            )

        update_data = data.dict(exclude_unset=True)

        for key, value in update_data.items():
            setattr(revenue, key, value)

        db.commit()
        db.refresh(revenue)
        log_action(
            db, user_id, role, "UPDATE", "Revenue",revenue.id, data.model_dump(mode="json")
        )
        updated_revenue = {
            column.name: getattr(revenue, column.name)
            for column in revenue.__table__.columns
        }

        return {
            "success": True,
            "message": "Revenue updated successfully",
            "data": updated_revenue
        }


    except Exception as e:
        db.rollback()
        print(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )



