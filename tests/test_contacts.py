import pytest

def test_contacts_lifecycle(auth_client, test_user):
    # 1. Create an Account first (since Contact requires a parent account_id)
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
        "pincode": "400001",
        "custom_fields": {"linkedin": "linkedin.com/in/johndoe"}
    }
    create_response = auth_client.post("/contacts", json=contact_payload)
    assert create_response.status_code == 200
    # Wait, the create endpoint returns the Contact object directly?
    # Let's check src/controllers/contact.py: create_contact returns the new_contact object.
    # The router wrapper returns contact:
    # return create_contact(data=data, db=db, user_id=user_id, user_role=user_role)
    # So create_response.json() should contain id.
    contact_data = create_response.json()
    assert "id" in contact_data
    contact_id = contact_data["id"]
    assert contact_data["first_name"] == "John"
    assert contact_data["last_name"] == "Doe"

    # 3. List all contacts and verify the created contact exists in the response
    list_response = auth_client.get("/contacts")
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert "data" in list_data
    assert any(c["id"] == str(contact_id) for c in list_data["data"])

    # 4. Fetch the contact by ID (detail view logic we optimized)
    detail_response = auth_client.get(f"/contacts?contact_id={contact_id}")
    assert detail_response.status_code == 200
    detail_data = detail_response.json()
    assert "data" in detail_data
    assert len(detail_data["data"]) == 1
    fetched_contact = detail_data["data"][0]
    assert fetched_contact["id"] == str(contact_id)
    assert fetched_contact["parent_account"] is not None
    assert fetched_contact["parent_account"]["id"] == str(account_id)

    # 5. Update the contact details
    update_payload = {
        "first_name": "Johnny",
        "designation": "Director",
        "city": "Pune"
    }
    update_response = auth_client.put(f"/contacts/{contact_id}", json=update_payload)
    assert update_response.status_code == 200
    update_data = update_response.json()
    assert update_data["message"] == "update-success"
    updated_contact = update_data["updated_contact"]
    assert updated_contact["first_name"] == "Johnny"
    assert updated_contact["designation"] == "Director"
    assert updated_contact["city"] == "Pune"
