from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _signup_and_login(email: str) -> str:
    signup = client.post(
        "/auth/signup",
        json={
            "name": "Call Pref User",
            "email": email,
            "password": "Test@12345",
            "phone_number": "+919843731545",
            "timezone": "Asia/Kolkata",
            "preferred_language": "English",
        },
    )
    assert signup.status_code in {200, 201}, signup.text
    login = client.post("/auth/login", json={"email": email, "password": "Test@12345"})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def test_call_preferences_defaults_and_update() -> None:
    token = _signup_and_login(f"call-prefs-user-{datetime.now(timezone.utc).timestamp()}@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/call-preferences", headers=headers)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["call_slot_1_time"] == "09:00"
    assert payload["call_slot_2_time"] == "13:00"
    assert payload["call_slot_3_time"] == "19:00"
    assert payload["minimum_new_emails_to_call"] == 1
    assert payload["skip_if_no_new_emails"] is True

    update = client.put(
        "/call-preferences",
        headers=headers,
        json={
            "timezone": "Asia/Kolkata",
            "call_slot_1_time": "08:30",
            "call_slot_1_enabled": True,
            "call_slot_2_time": "12:15",
            "call_slot_2_enabled": False,
            "call_slot_3_time": "18:45",
            "call_slot_3_enabled": True,
            "minimum_new_emails_to_call": 3,
            "skip_if_no_new_emails": True,
            "avoid_repeating_delivered_emails": True,
        },
    )
    assert update.status_code == 200, update.text
    updated = update.json()
    assert updated["call_slot_1_time"] == "08:30"
    assert updated["call_slot_2_enabled"] is False
    assert updated["minimum_new_emails_to_call"] == 3

    invalid_time = client.put("/call-preferences", headers=headers, json={"call_slot_1_time": "25:00"})
    assert invalid_time.status_code in {400, 422}

    invalid_minimum = client.put("/call-preferences", headers=headers, json={"minimum_new_emails_to_call": 2})
    assert invalid_minimum.status_code in {400, 422}
