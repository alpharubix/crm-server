import pytest
from fastapi.testclient import TestClient

def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello World"}

def test_login_success(client, test_user):
    # test_user created by fixture with password "Secret123!"
    payload = {
        "email": "testuser@example.com",
        "password": "Secret123!"
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 200
    assert response.json() == {"message": "Login Successful"}
    assert "token" in response.cookies

def test_login_invalid_password(client, test_user):
    payload = {
        "email": "testuser@example.com",
        "password": "WrongPassword123"
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 401
    assert "Invalid Credentials" in response.json().get("detail", "")

def test_login_user_not_found(client):
    payload = {
        "email": "nonexistentuser@example.com",
        "password": "SomePassword"
    }
    response = client.post("/auth/login", json=payload)
    assert response.status_code == 404
    assert "Account not found" in response.json().get("detail", "")

def test_create_account(auth_client, test_user):
    # auth_client is pre-authenticated with test_user
    payload = {
        "first_name": "TestFirst",
        "last_name": "TestLast",
        "email": "unique.test.account@example.com",
        "phone": "9876543210",
        "account_name": "Test Account Corp",
        "account_status": "Awareness",
        "account_stage": "Initial Pitch",
        "account_owner_id": str(test_user.id)
    }
    response = auth_client.post("/accounts", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["message"] == "Account created successfully"

def test_list_accounts(auth_client):
    # Standard list view query
    response = auth_client.get("/accounts")
    assert response.status_code == 200
    res_data = response.json()
    assert "data" in res_data
    assert "page_info" in res_data

def test_get_account_by_id_with_mongodb_notes(auth_client, test_user, mongo_db):
    # 1. Create account
    payload = {
        "first_name": "AccountWithNotes",
        "last_name": "Test",
        "email": "notes.account@example.com",
        "phone": "9876543211",
        "account_name": "Account Notes Corp",
        "account_status": "Awareness",
        "account_stage": "Initial Pitch",
        "account_owner_id": str(test_user.id)
    }
    response = auth_client.post("/accounts", json=payload)
    assert response.status_code == 200
    account_id = response.json()["id"]

    # Seed a note in test MongoDB collection
    mongo_db["Notes"].insert_one({
        "Parent_Id": {
            "id": str(account_id),
            "module": "Accounts"
        },
        "Note_Title": "Test Title",
        "Note_Content": "Test Content",
        "Created_By": "Test User"
    })

    # 2. Get detailed account view (which triggers MongoDB query for Notes)
    response = auth_client.get(f"/accounts?account_id={account_id}")
    assert response.status_code == 200
    res_data = response.json()
    
    # Assert account data exists
    assert "data" in res_data
    assert len(res_data["data"]) == 1
    
    # Assert notes fetched from MongoDB exist
    account_details = res_data["data"][0]
    assert "notes" in account_details
    assert len(account_details["notes"]) == 1
    assert account_details["notes"][0]["Note_Title"] == "Test Title"

def test_contacts_lifecycle(auth_client, test_user):
    # 1. Create an Account first
    account_payload = {
        "first_name": "ContactParent",
        "last_name": "Account",
        "email": "contact.parent@example.com",
        "phone": "9876543212",
        "account_name": "Contact Parent Corp",
        "account_status": "Awareness",
        "account_stage": "Initial Pitch",
        "account_owner_id": str(test_user.id)
    }
    account_response = auth_client.post("/accounts", json=account_payload)
    assert account_response.status_code == 200
    account_id = account_response.json()["id"]

    # 2. Create a Contact linked to this Account
    contact_payload = {
        "first_name": "John",
        "last_name": "Doe",
        "designation": "Manager",
        "account_id": account_id,
        "email": "johndoe@example.com",
        "mobile": "9999988888",
        "phone": "1234567890",
        "city": "Mumbai",
        "state": "Maharashtra",
        "country": "India",
        "pincode": "400001"
    }
    create_response = auth_client.post("/contacts", json=contact_payload)
    assert create_response.status_code == 200
    contact_data = create_response.json()
    assert "id" in contact_data
    contact_id = contact_data["id"]

    # 3. List contacts
    list_response = auth_client.get("/contacts")
    assert list_response.status_code == 200
    assert "data" in list_response.json()

    # 4. Detail contact
    detail_response = auth_client.get(f"/contacts?contact_id={contact_id}")
    assert detail_response.status_code == 200
    assert len(detail_response.json()["data"]) == 1

    # 5. Update contact
    update_payload = {"first_name": "Johnny"}
    update_response = auth_client.put(f"/contacts/{contact_id}", json=update_payload)
    assert update_response.status_code == 200

def test_users_lifecycle(auth_client, test_user):
    # 1. List user mentions
    mentions_response = auth_client.get("/user/mentions")
    assert mentions_response.status_code == 200
    assert "data" in mentions_response.json()

    # 2. Filter users
    filter_response = auth_client.get("/user/filter")
    assert filter_response.status_code == 200
    assert "data" in filter_response.json()

def test_notes_lifecycle(auth_client, test_user, mongo_db):
    # Seed MongoDB with a dummy user doc, since insert_notes does a lookup on user_id
    mongo_db["users"].insert_one({
        "id": str(test_user.id),
        "first_name": "Test",
        "email": "testuser@example.com"
    })

    # 1. Create a Note for account ID 99999
    note_payload = {
        "id": "99999",
        "note": "This is a direct test note content.",
        "module": "Accounts"
    }
    response = auth_client.post("/notes", json=note_payload)
    assert response.status_code == 201
    assert response.json() == {"message": "Note saved successfully"}

    # 2. Get the note via our GET endpoint we fixed
    notes_response = auth_client.get("/notes/99999")
    assert notes_response.status_code == 200
    notes_data = notes_response.json()
    assert "data" in notes_data
    assert len(notes_data["data"]) == 1
    assert notes_data["data"][0]["Note_Content"] == "This is a direct test note content."
