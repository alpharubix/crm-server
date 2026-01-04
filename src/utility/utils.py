import os
import secrets
import string
import jwt
import bcrypt
from ..config import settings

def generate_secure_password(length: int = 16, include_symbols: bool = True) -> str:
    """
    Generates a cryptographically secure random password.
    Ensures at least one lowercase, uppercase, and digit is present.
    """
    if length < 8:
        raise ValueError("Password length should be at least 8 characters.")

    # Define character sets
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    symbols = string.punctuation if include_symbols else ""

    all_chars = lower + upper + digits + symbols

    while True:
        # Generate a random password
        password = ''.join(secrets.choice(all_chars) for _ in range(length))

        # Check constraints (Must have upper, lower, and digit)
        if (any(c in lower for c in password)
                and any(c in upper for c in password)
                and any(c in digits for c in password)):
            return password

def get_hashed_password(password: str) -> str:
    hashed_bytes = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=7))
    hashed_password_str = hashed_bytes.decode('utf-8')
    return hashed_password_str


def is_password_correct(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'),hashed_password.encode('utf-8'))


def get_jwt_token(user_id:int,role:str):
      token = jwt.encode({'user_id':user_id,'role':role},settings.JWT_SECRET_KEY,algorithm='HS256')
      return token

def get_decoded_jwt_token(token:str) -> dict:
    return jwt.decode(token,settings.JWT_SECRET_KEY,algorithms=['HS256'])