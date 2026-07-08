import pytest

def test_notes_lifecycle(auth_client, test_user, mongo_db):
    # 1. Create an Account first
    account_payload = {
        "first_name": "NoteParent",
        "last_name": "Account",
        "email": "note.parent@example.com",
        "phone": "9876543213",
        "account_name": "Note Parent Corp",
        "account_status": "Awareness",
        "account_stage": "Initial Pitch",
        "account_owner_id": str(test_user.id)
    }
    account_response = auth_client.post("/accounts", json=account_payload)
    assert account_response.status_code == 200
    account_id = account_response.json()["id"]

    # Seed MongoDB with a dummy user doc, since insert_notes does a lookup on user_id
    # src/controllers/notes.py:
    # user_doc = user_coll.find_one({"id": str(user_id)}, ...)
    mongo_db["users"].insert_one({
        "id": str(test_user.id),
        "first_name": "Test",
        "email": "testuser@example.com"
    })

    # 2. Create a Note linked to the Account
    note_payload = {
        "id": str(account_id),
        "note": "This is a test note for our account lifecycle.",
        "module": "Accounts"
    }
    response = auth_client.post("/notes", json=note_payload)
    assert response.status_code == 201
    assert response.json() == {"message": "Note saved successfully"}

    # 3. Get detailed account view to verify the note was attached
    detail_response = auth_client.get(f"/accounts?account_id={account_id}")
    assert detail_response.status_code == 200
    detail_data = detail_response.json()
    assert "data" in detail_data
    assert len(detail_data["data"]) == 1
    
    account_details = detail_data["data"][0]
    assert "notes" in account_details
    assert len(account_details["notes"]) == 1
    assert account_details["notes"][0]["Note_Content"] == "This is a test note for our account lifecycle."
