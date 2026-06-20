from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database.session import Base, engine
from app.main import app


client = TestClient(app)

Base.metadata.create_all(bind=engine)


def _signup_and_login(email: str) -> str:
    signup = client.post(
        "/auth/signup",
        json={
            "name": "Priority Contact User",
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


def test_priority_contacts_crud_and_duplicate_block() -> None:
    email = f"priority-contact-{uuid4()}@example.com"
    token = _signup_and_login(email)
    headers = {"Authorization": f"Bearer {token}"}

    empty = client.get("/priority-contacts", headers=headers)
    assert empty.status_code == 200, empty.text
    assert empty.json() == []

    create = client.post(
        "/priority-contacts",
        headers=headers,
        json={
            "display_name": "Mom",
            "email_address": "mom@example.com",
            "relationship": "Family",
            "priority_level": 2,
            "notes": "Call soon",
        },
    )
    assert create.status_code == 200, create.text
    created = create.json()
    assert created["display_name"] == "Mom"
    assert created["email_address"] == "mom@example.com"
    assert created["relationship"] == "Family"
    assert created["priority_level"] == 2

    duplicate = client.post(
        "/priority-contacts",
        headers=headers,
        json={
            "display_name": "Mother",
            "email_address": "MOM@example.com",
            "relationship": "Family",
        },
    )
    assert duplicate.status_code == 409, duplicate.text

    contact_id = created["id"]
    update = client.put(
        f"/priority-contacts/{contact_id}",
        headers=headers,
        json={
            "display_name": "Mother",
            "relationship": "Mentor",
            "priority_level": 3,
            "notes": "Updated note",
        },
    )
    assert update.status_code == 200, update.text
    updated = update.json()
    assert updated["display_name"] == "Mother"
    assert updated["relationship"] == "Mentor"
    assert updated["priority_level"] == 3

    delete = client.delete(f"/priority-contacts/{contact_id}", headers=headers)
    assert delete.status_code == 200, delete.text
    assert delete.json()["email_address"] == "mom@example.com"

    final = client.get("/priority-contacts", headers=headers)
    assert final.status_code == 200, final.text
    assert final.json() == []
