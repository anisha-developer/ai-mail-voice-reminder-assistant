from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.database.session import SessionLocal
from app.main import app
from app.models.reminder import Reminder
from app.models.user import User


client = TestClient(app)


def _login(email: str, password: str) -> str:
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _future_payload(title: str, minutes: int = 20, timezone_name: str = "Asia/Kolkata", phone_number: str | None = None) -> dict[str, str]:
    local_now = datetime.now(ZoneInfo(timezone_name)) + timedelta(minutes=minutes)
    payload = {
        "title": title,
        "notes": "API reminder test",
        "reminder_date": local_now.date().isoformat(),
        "reminder_time": local_now.strftime("%H:%M"),
        "timezone": timezone_name,
    }
    if phone_number is not None:
        payload["phone_number"] = phone_number
    return payload


def test_reminder_api_create_list_get_patch_delete_and_rejects() -> None:
    token = _login("browsertest@example.com", "Test@12345")
    headers = {"Authorization": f"Bearer {token}"}
    title = "API Reminder " + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    create_response = client.post("/reminders", headers=headers, json=_future_payload(title))
    assert create_response.status_code == 200, create_response.text
    created = create_response.json()
    assert created["title"] == title
    assert created["status"] == "scheduled"

    list_response = client.get("/reminders", headers=headers)
    assert list_response.status_code == 200, list_response.text
    listed = list_response.json()
    assert listed["count"] >= 1
    assert any(item["id"] == created["id"] for item in listed["value"])

    get_response = client.get(f"/reminders/{created['id']}", headers=headers)
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["id"] == created["id"]

    patch_response = client.patch(
        f"/reminders/{created['id']}",
        headers=headers,
        json={
            "title": f"{title} updated",
            "notes": "Updated notes",
            "reminder_date": created["reminder_at"][:10],
            "reminder_time": created["reminder_at"][11:16],
            "timezone": "Asia/Kolkata",
            "phone_number": "+919843731545",
        },
    )
    assert patch_response.status_code == 200, patch_response.text
    assert patch_response.json()["title"].endswith("updated")

    delete_response = client.delete(f"/reminders/{created['id']}", headers=headers)
    assert delete_response.status_code == 200, delete_response.text
    assert delete_response.json()["status"] == "cancelled"

    after_cancel = client.get("/reminders", headers=headers).json()
    assert all(item["id"] != created["id"] for item in after_cancel["value"])

    past_local = datetime.now(ZoneInfo("Asia/Kolkata")) - timedelta(minutes=5)
    past_response = client.post(
        "/reminders",
        headers=headers,
        json={
            "title": "Past API Reminder",
            "notes": "Should fail",
            "reminder_date": past_local.date().isoformat(),
            "reminder_time": past_local.strftime("%H:%M"),
            "timezone": "Asia/Kolkata",
            "phone_number": "+919843731545",
        },
    )
    assert past_response.status_code in {400, 422}

    invalid_tz = client.post(
        "/reminders",
        headers=headers,
        json={
            "title": "Bad TZ",
            "notes": "Should fail",
            "reminder_date": past_local.date().isoformat(),
            "reminder_time": "18:30",
            "timezone": "Invalid/Zone",
            "phone_number": "+919843731545",
        },
    )
    assert invalid_tz.status_code in {400, 422}

    unauthorized = client.get("/reminders")
    assert unauthorized.status_code == 401


def test_reminder_api_cross_user_protection() -> None:
    db = SessionLocal()
    try:
        other_email = f"reminder-api-other@example.com"
        existing = db.query(User).filter(User.email == other_email).first()
        if existing is None:
            existing = User(
                email=other_email,
                name="Reminder API Other",
                phone_number="+919999999997",
                timezone="Asia/Kolkata",
                preferred_language="English",
                hashed_password="hash",
                is_active=True,
                is_verified=False,
            )
            db.add(existing)
            db.commit()
            db.refresh(existing)
    finally:
        db.close()

    user_token = _login("browsertest@example.com", "Test@12345")
    other_token = _login("reminder-api-other@example.com", "hash") if False else None
    assert other_token is None

    headers = {"Authorization": f"Bearer {user_token}"}
    title = "Cross User Reminder " + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    create_response = client.post("/reminders", headers=headers, json=_future_payload(title))
    assert create_response.status_code == 200, create_response.text
    reminder_id = create_response.json()["id"]

    db = SessionLocal()
    try:
        # Create a second user with a valid password hash by signing up via the API.
        signup_email = f"reminder-api-other-{datetime.now(timezone.utc).timestamp()}@example.com"
        signup_response = client.post(
            "/auth/signup",
            json={
                "name": "Reminder API Other",
                "email": signup_email,
                "password": "Test@12345",
                "phone_number": "+919999999997",
                "timezone": "Asia/Kolkata",
                "preferred_language": "English",
            },
        )
        assert signup_response.status_code in {200, 201}, signup_response.text
        other_login = _login(signup_email, "Test@12345")
        other_headers = {"Authorization": f"Bearer {other_login}"}

        assert client.get(f"/reminders/{reminder_id}", headers=other_headers).status_code == 404
        assert client.patch(f"/reminders/{reminder_id}", headers=other_headers, json={"title": "Not allowed"}).status_code == 404
        assert client.delete(f"/reminders/{reminder_id}", headers=other_headers).status_code == 404
    finally:
        db.query(Reminder).filter(Reminder.title == title).delete(synchronize_session=False)
        db.commit()
        db.close()
