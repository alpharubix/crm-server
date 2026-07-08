import pytest
from src.utility.utils import generate_secure_password, get_hashed_password, is_password_correct

def test_generate_secure_password_length():
    # Unit Test: Verifies password generation length constraint in isolation
    pwd = generate_secure_password(length=12)
    assert len(pwd) == 12

def test_generate_secure_password_complexity():
    # Unit Test: Verifies that lowercase, uppercase, and digits are always present
    pwd = generate_secure_password(length=16)
    
    assert any(c.islower() for c in pwd)
    assert any(c.isupper() for c in pwd)
    assert any(c.isdigit() for c in pwd)

def test_generate_secure_password_too_short():
    # Unit Test: Verifies exception boundaries are enforced correctly
    with pytest.raises(ValueError):
        generate_secure_password(length=5)

def test_password_hashing_and_verification():
    # Unit Test: Verifies cryptography logic matches without any database dependency
    raw_password = "MySafePassword123!"
    hashed = get_hashed_password(raw_password)
    
    assert hashed != raw_password
    assert is_password_correct(raw_password, hashed) is True
    assert is_password_correct("WrongPassword", hashed) is False
