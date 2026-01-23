from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse, Response

from src.models.user import User
from src.schemas.authentication import Login
from src.utility.utils import get_jwt_token, is_password_correct


def validate_login(body: Login, db: Session):
    email = body.email
    password = body.password
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            raise HTTPException(status_code=404, detail="Account not found")
        else:
            hashed_password = user.password
            print(hashed_password)
            print(password)
            print(repr(password))
            if not is_password_correct(
                password=password, hashed_password=hashed_password
            ):
                raise HTTPException(status_code=401, detail="Invalid Credentials")
            else:
                token = get_jwt_token(user.id, user.role)
                response = JSONResponse(
                    status_code=200, content={"message": "Login Successful"}
                )

                response.set_cookie(
                    key="token",
                    value=token,
                    httponly=True,
                    secure=True,
                    samesite="none",
                )
                return response
    except HTTPException as error:
        print(error)
        raise HTTPException(status_code=error.status_code, detail=error.detail)
    except Exception as error:
        print(error)
        raise HTTPException(status_code=500, detail="Internal Server Error")


class MANAGERID:
    MANAGER_EXECUTIVES_MAP = {
        # Namrata
        3899927000000318361: [
            3899927000000318361,  #Namrata
            3899927000005965018,  # Arjun
            3899927000004429017,  # Sandeep
            3899927000004808001,  # Ayush
            3899927000007673012,  # Honappa
            3899927000005114004,  # Manjunath
            3899927000005114020,  # Digamber
            3899927000005965050,  # Sahil
        ],
        # Sutapa Roy
        3899927000005114050: [
            3899927000005114050,  #sutapa
            3899927000005965018,  # Arjun
            3899927000004429017,  # Sandeep
            3899927000004808001,  # Ayush
            3899927000007673012,  # Honappa
            3899927000005114004,  # Manjunath
            3899927000005114020,  # Digamber
            3899927000005965050,  # Sahil
        ],
        # Manjunath
        3899927000005114004: [
            3899927000005114004,  #manjunath
            3899927000005965018,  # Arjun
            3899927000004429017,  # Sandeep
            3899927000007673012,  # Honappa
        ],
        # Digamber
        3899927000005114020: [
            3899927000005114020,   #digambar
            3899927000004808001,  # Ayush
            3899927000005965018,  # Arjun
            3899927000007673012,  # Honappa
            3899927000005114004,  # Manjunath
            3899927000004429017,  # Sandeep
            3899927000005965050,  # Sahil
        ],
        # manager_id: [executive_ids]
    }

