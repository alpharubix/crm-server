import pytest
from src.models.deal import Deal

def test_revenue_lifecycle(auth_client, test_user, db_session):
    # 1. Create an Account first
    account_payload = {
        "first_name": "RevenueParent",
        "last_name": "Account",
        "email": "revenue.parent@example.com",
        "phone": "9876543214",
        "account_name": "Revenue Parent Corp",
        "account_status": "Awareness",
        "account_stage": "Initial Pitch",
        "account_owner_id": str(test_user.id)
    }
    account_response = auth_client.post("/accounts", json=account_payload)
    assert account_response.status_code == 200
    account_id = account_response.json()["id"]

    # 2. Insert a Deal in the DB referencing the Account
    deal = Deal(
        account_id=account_id,
        deal_owner_id=test_user.id,
        deal_name="Revenue Test Deal",
        deal_stage="Proposal",
        deal_status="Active"
    )
    db_session.add(deal)
    db_session.commit()

    # 3. Create a Revenue record referencing the Deal
    revenue_payload = {
        "deal_id": deal.id,
        "account_name": "Revenue Parent Corp",
        "lender_name": "Test Bank",
        "reference_number": "REF-12345",
        "income_booking_date": "2026-06-18",
        "type_of_revenue": "Payout",
        "amount": 10000.0,
        "gst_amount": 1800.0
    }
    create_response = auth_client.post("/revenue", json=revenue_payload)
    assert create_response.status_code == 200
    res_data = create_response.json()
    assert res_data["success"] is True
    assert "data" in res_data
    revenue_id = res_data["data"]["id"]

    # 4. List all revenues
    list_response = auth_client.get("/revenue")
    assert list_response.status_code == 200
    list_data = list_response.json()
    assert list_data["success"] is True
    assert "data" in list_data
    assert any(str(r["id"]) == str(revenue_id) for r in list_data["data"])

    # 5. Fetch single revenue by ID (the detail path we optimized)
    detail_response = auth_client.get(f"/revenue?revenue_id={revenue_id}")
    assert detail_response.status_code == 200
    detail_data = detail_response.json()
    assert detail_data["success"] is True
    assert len(detail_data["data"]) == 1
    fetched_revenue = detail_data["data"][0]
    assert str(fetched_revenue["id"]) == str(revenue_id)
    assert fetched_revenue["revenue_owner"] is not None
    assert fetched_revenue["revenue_owner"]["full_name"] == test_user.full_name

    # 6. Update the revenue
    update_payload = {
        "lender_name": "Updated Bank",
        "amount": 12000.0
    }
    update_response = auth_client.patch(f"/revenue/{revenue_id}", json=update_payload)
    assert update_response.status_code == 200
    update_data = update_response.json()
    assert update_data["success"] is True
    assert update_data["data"]["lender_name"] == "Updated Bank"
    assert update_data["data"]["amount"] == 12000.0
