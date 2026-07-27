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
    # symbols = string.punctuation if include_symbols else ""

    all_chars = lower + upper + digits

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
        "source_type",
        "source_date",
        "business_status",
        "distributor_code",
        "type_of_business",
        "industry",
        "business_premise_city",
        "business_premise_state",
        "business_premise_pincode",
        "waba_interested",
        "call_back_date_time",
        "gstn",
        "pan",
    }


def get_deal_headers():
    return {
        "id",
        "account_id",
        "deal_type",
        "amount_required",
        "loan_type",
        "deal_status",
        "deal_stage",
        "lender_name",
        "partner_name",
        "lender_login_type",
        "deal_status_closing",
        "deal_expected_closing",
        "deal_status_closing",
        "deal_owner_id",
    }


def get_ticket_headers():
    return {
        "id",
        "deal_id",
        "ticket_login",
        "lender_name",
        "potential",
        "lender_login_type",
        "lender_login_date",
        "partner_name",
        "targeted_disbursement_date",
        "type_of_loan",
        "disbursement_date",
        "ticket_status",
        "ticket_stage",
        "approved_amount",
        "sanction_amount",
        "processing_fees",
        "disbursed_amount",
        "pf_percentage",
        "tenure",
        "insurance_amount",
        "loan_start_date",
        "rate_of_interest",
        "loan_end_date",
        "interest_type",
        "customer_rejection_reason",
        "customer_rejection_status_explanation",
        "lender_rejection_status_explanation",
    }
