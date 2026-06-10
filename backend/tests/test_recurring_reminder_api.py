from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _auth_headers() -> dict[str, str]:
    response = client.post(
        "/auth/login",
        json={"email": "browsertest@example.com", "password": "Test@12345"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_recurring_reminder_crud_and_actions() -> None:
    headers = _auth_headers()
    title = f"Recurring API Test {uuid4()}"
    create_response = client.post(
        "/recurring-reminders",
        json={
            "title": title,
            "notes": "API test",
            "timezone": "Asia/Kolkata",
            "repeat_type": "daily",
            "time_of_day": "09:00",
            "source_type": "manual",
        },
        headers=headers,
    )
    assert create_response.status_code == 200
    rule_id = create_response.json()["id"]

    list_response = client.get("/recurring-reminders", headers=headers)
    assert list_response.status_code == 200
    assert any(item["id"] == rule_id for item in list_response.json()["value"])

    get_response = client.get(f"/recurring-reminders/{rule_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["title"] == title

    pause_response = client.post(f"/recurring-reminders/{rule_id}/pause", headers=headers)
    assert pause_response.status_code == 200
    assert pause_response.json()["status"] == "paused"

    resume_response = client.post(f"/recurring-reminders/{rule_id}/resume", headers=headers)
    assert resume_response.status_code == 200
    assert resume_response.json()["status"] == "active"

    cancel_response = client.post(f"/recurring-reminders/{rule_id}/cancel", headers=headers)
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    occurrences_response = client.get(f"/recurring-reminders/{rule_id}/occurrences", headers=headers)
    assert occurrences_response.status_code == 200

    delete_response = client.delete(f"/recurring-reminders/{rule_id}", headers=headers)
    assert delete_response.status_code == 200
