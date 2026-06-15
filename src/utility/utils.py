import secrets
import string
from datetime import datetime, timedelta

import bcrypt
import jwt

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
    # symbols = string.punctuation if include_symbols else ""

    all_chars = lower + upper + digits

    while True:
        # Generate a random password
        password = "".join(secrets.choice(all_chars) for _ in range(length))

        # Check constraints (Must have upper, lower, and digit)
        if (
            any(c in lower for c in password)
            and any(c in upper for c in password)
            and any(c in digits for c in password)
        ):
            return password


def get_hashed_password(password: str) -> str:
    hashed_bytes = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=7))
    hashed_password_str = hashed_bytes.decode("utf-8")
    return hashed_password_str


def is_password_correct(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_jwt_token(user_id, role, full_name, email):
    payload = {
        "user_id": str(user_id),
        "role": role,
        "full_name": full_name,
        "email": email,
        "exp": datetime.utcnow() + timedelta(days=30),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


def get_decoded_jwt_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])


def get_account_headers():
    return {
        "id",
        "first_name",
        "last_name",
        "email",
        "phone",
        "account_name",
        "account_owner_id",
        "account_status",
        "account_stage",
        "source",
        "business_status",
        "distributor_code",
        "type_of_business",
        "industry",
        "city",
        "state",
        "pincode",
        "waba_interested",
        "call_back_date_time",
    }
