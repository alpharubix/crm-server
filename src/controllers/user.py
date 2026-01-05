from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse
from ..models.user import User
from ..schemas.user import ExistingUser
from ..utility.utils import generate_secure_password,get_hashed_password


def insert_already_existing_user(data:ExistingUser,db):
    try:
        if db.query(User).filter(User.email == data.email).first():
            return JSONResponse(status_code=400,content={"message":"User already exists"})
        else:
            #define role for this user
            role = None #role will be none initially
            if data.role == "CEO" and data.profile == 'Administrator':
                role = 'super_admin'
            elif data.role == "Manager" and data.profile == 'Administrator':
                role = 'admin'
            elif data.role == "Manager" and data.profile == 'Standard':
                role = 'executive'

            #generate the password and store it
            password = generate_secure_password(8)
            print(f"Generaed new password for {data.full_name} =>",password)
            hashed_password = get_hashed_password(password)
            print("hashed_password=>",hashed_password)

            user = User(id=data.id,full_name=data.full_name,email=data.email,role=role,zuid=data.zuid,password=hashed_password,created_time=data.created_time,
                        modified_time=data.modified_time,created_by_id=data.created_by_id,modified_by_id=data.modified_by_id)
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



