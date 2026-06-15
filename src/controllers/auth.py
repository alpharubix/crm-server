from fastapi import HTTPException
from sqlalchemy.orm import Session
from starlette.responses import JSONResponse

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
                token = get_jwt_token(user.id, user.role, user.full_name, user.email)
                response = JSONResponse(
                    status_code=200, content={"message": "Login Successful"}
                )

                response.set_cookie(
                    key="token",
                    value=token,
                    httponly=True,
                    secure=True,
                    samesite="none",
                    max_age=60 * 60 * 24 * 30,  # 30 days
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
            3899927000000240595,  # Chiranjeevi B S
            3899927000000498931,  # Karthik H M
            3899927000000647914,  # Prajwal G P
            3899927000000208140,  # Shivaraj P N
            3899927000000488938,  # Nagaraj
            3899927000000318361,  # Namrata
            3899927000005965018,  # Arjun
            3899927000004429017,  # Sandeep
            3899927000004808001,  # Ayush
            3899927000007673012,  # Honappa
            3899927000000795843,  # Prashanth
            3899927000005114004,  # Manjunath
            3899927000005114020,  # Digamber
            3899927000005965050,  # Sahil
            3899927000000221552,  # Sarada
            3899927000000452950,  # Vinod
        ],
        # Ashwini R
        3899927000000319812: [
            3899927000000319812,  # Ashwini R
            3899927000000240595,  # Chiranjeevi B S
            3899927000000498931,  # Karthik H M
            3899927000000647914,  # Prajwal G P
            3899927000000208140,  # Shivaraj P N
            3899927000000488938,  # Nagaraj
            3899927000005965018,  # Arjun
            3899927000004429017,  # Sandeep
            3899927000004808001,  # Ayush
            3899927000007673012,  # Honappa
            3899927000000795843,  # Prashanth
            3899927000005114004,  # Manjunath
            3899927000005114020,  # Digamber
            3899927000005965050,  # Sahil
            3899927000000452950,  # Vinod
        ],
        # Sutapa Roy
        3899927000005114050: [
            3899927000000240595,  # Chiranjeevi B S
            3899927000000498931,  # Karthik H M
            3899927000000647914,  # Prajwal G P
            3899927000000208140,  # Shivaraj P N
            3899927000000488938,  # Nagaraj
            3899927000005114050,  # sutapa
            3899927000005965018,  # Arjun
            3899927000004429017,  # Sandeep
            3899927000004808001,  # Ayush
            3899927000007673012,  # Honappa
            3899927000000795843,  # Prashanth
            3899927000005114004,  # Manjunath
            3899927000005114020,  # Digamber
            3899927000005965050,  # Sahil
            3899927000000452950,  # Vinod
        ],
        # Manjunath
        3899927000005114004: [
            3899927000005114004,  # manjunath
            3899927000005965018,  # Arjun
            3899927000004429017,  # Sandeep
        ],
        # Prathap
        3899927000000851906: [
            3899927000000851906,  # Prathap
            3899927000007673012,  # Honappa
            3899927000000795843,  # Prashanth
            3899927000000452950,  # Vinod
        ],
        # Nagaraj
        3899927000000488938: [
            3899927000000240595,  # Chiranjeevi B S
            3899927000000498931,  # Karthik H M
            3899927000000647914,  # Prajwal G P
            3899927000000208140,  # Shivaraj P N
            3899927000000488938,  # Nagaraj
        ],
        # Pranay
        3899927000000650180: [
            3899927000000240595,  # Chiranjeevi B S
            3899927000000498931,  # Karthik H M
            3899927000000647914,  # Prajwal G P
            3899927000000208140,  # Shivaraj P N
            3899927000000488938,  # Nagaraj
            3899927000005965018,  # Arjun
            3899927000004429017,  # Sandeep
            3899927000004808001,  # Ayush
            3899927000007673012,  # Honappa
            3899927000000795843,  # Prashanth
            3899927000005114004,  # Manjunath
            3899927000005114020,  # Digamber
            3899927000005965050,  # Sahil
            3899927000000650180,  # Pranay
            3899927000000452950,  # Vinod
        ],
        # # Digamber
        # 3899927000005114020: [
        #     3899927000005114020,   #digambar
        #     3899927000004808001,  # Ayush
        #     3899927000005965018,  # Arjun
        #     3899927000007673012,  # Honappa
        #     3899927000005114004,  # Manjunath
        #     3899927000004429017,  # Sandeep
        #     3899927000005965050,  # Sahil
        # ],
        # manager_id: [executive_ids]
    }


users = {  # users for fast lookup
    3899927000003497001: "Sudha S",
    3899927000004429001: "Somasundaram S",
    3899927000005114034: "Mamatha Rani",
    3899927000005114066: "Ashwini R",
    3899927000005965034: "Nitesh Prasad",
    3899927000005965066: "Savitha G",
    3899927000005965080: "Dhivyesh S Patel",
    3899927000007961681: "Kavya K B",
    3899927000007961697: "Hemanta kumar Palai",
    3899927000007961713: "Santhosh S",
    3899927000007961727: "Pallavi Gattu",
    3899927000007961740: "Mailari Kumar",
    3899927000007961754: "Bhuvana R",
    3899927000007961770: "Timmalamma",
    3899927000007961784: "Mitali Dutta",
    3899927000013394001: "Ashwini R",
    3899927000015079001: "Kalyan Kumar",
    3899927000046992001: "Irudhaya John",
    3899927000124423001: "Tech Manager",
    3899927000005114050: "Sutapa Roy",
    3899927000005114020: "Digamber Pandey",
    3899927000005965018: "Arjun J",
    3899927000004429017: "Sandip Kumar Jena",
    3899927000004808001: "Ayush Dingane",
    3899927000007673012: "Honnapa Nayak",
    3899927000005114004: "Manjunath Jain",
    3899927000005965050: "Sahil Kispotta",
    3899927000000318361: "Namrata Srivastava",
    3899927000000201013: "Anslem Prathap",
    3899927000005965002: "Subhasini T S",
    3899927000000615348: "Ashok M",
    3899927000000964875: "Suraj Gupta",
    3899927000000882594: "Myisa Beiucy",
    3899927000000723465: "Kaveri Metri",
    3899927000000488938: "Nagaraj Hodmany",
    3899927000000208140: "Shivaraj P N",
    3899927000000647914: "Prajwal G P",
    3899927000000498931: "Karthik H M",
    3899927000000240595: "Chiranjeevi B S",
    3899927000000319812: "Ashwini R",
    3899927000000221552: "Sarada M",
    3899927000000650180: "Pranay Kumar",
    3899927000000795843: "Prashanth",
}
