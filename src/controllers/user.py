from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.controllers.auth import MANAGERID

from ..models.user import User
from ..schemas.user import ExistingUser
from ..utility.utils import generate_secure_password, get_hashed_password


def insert_already_existing_user(data: ExistingUser, db):
    try:
        if db.query(User).filter(User.email == data.email).first():
            return JSONResponse(
                status_code=400, content={"message": "User already exists"}
            )
        else:
            # define role for this user
            role = "admin"  # role will be CHANGE based on requirement
            # if data.role == "CEO" and data.profile == "Administrator":
            #     role = "super_admin"
            # elif data.role == "Manager" and data.profile == "Administrator":
            #     role = "admin"
            # elif data.role == "Manager" and data.profile == "Standard":
            #     role = "executive"

            # generate the password and store it
            password = generate_secure_password(8)
            print(f"Generaed new password for {data.full_name} =>", password)
            hashed_password = get_hashed_password(password)
            print("hashed_password=>", hashed_password)

            user = User(
                id=data.id,
                full_name=data.full_name,
                email=data.email,
                role=role,
                zuid=data.zuid,
                password=hashed_password,
                # created_time=data.created_time,
                # modified_time=data.modified_time,
                created_by_id=data.created_by_id,
                modified_by_id=data.modified_by_id,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            return user
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="internal server error")


def get_me(request:Request,db):
    role = request.state.role
    user_id = request.state.user_id
    try:
        user = db.query(User).filter(User.id == user_id).one()
        response = {'user_id':str(user_id),'role':role,'user_name':user.full_name,'email':user.email,'is_logged_in':True}
        return JSONResponse(status_code=200,content=response)
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="internal server error")



def get_user_filter(request: Request, db):
    # print(repr(request.state.user_id))
    # print(type(request.state.user_id))
    user_id = int(request.state.user_id)
    role = request.state.role
    # print(role)
    MANAGER_EXECUTIVE_MAP = MANAGERID().MANAGER_EXECUTIVES_MAP
    SUPER_ADMIN_AND_ADMIN_MAP = MANAGERID().SUPER_ADMIN_AND_ADMIN_MAP
    try:
        if role in ("super_admin", "admin"):
            admin_ids = list(SUPER_ADMIN_AND_ADMIN_MAP)

            users = (
                db.query(User.id, User.full_name).filter(User.id.in_(admin_ids)).all()
            )
            return {"data": users}
        elif role == "manager" or user_id in MANAGER_EXECUTIVE_MAP:
            executive_id = MANAGER_EXECUTIVE_MAP.get(user_id, [user_id])
            if user_id not in executive_id:
                executive_id = [user_id] + list(executive_id)
            users = db.query(User.id, User.full_name).filter(User.id.in_(executive_id)).all()
            return {'data': users}
        else:
            raise HTTPException(status_code=403, detail={"message": "You do not have permission to access this content", "success": False})
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail={"message": "internal server error"})


def get_all_users(db:Session):
    try:
        users = db.query(User.id,User.full_name).all()
        users_list = [
            {"id": user.id, "name": user.full_name}
            for user in users
        ]
        return {"data": users_list}
    except Exception:
        raise HTTPException(status_code=500, detail={"message":"internal server error"})
