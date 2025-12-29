import secrets
import string

import bcrypt


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