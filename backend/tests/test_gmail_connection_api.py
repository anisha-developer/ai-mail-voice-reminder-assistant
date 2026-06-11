from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.database.session import SessionLocal
from app.main import app
from app.models.gmail_connection import GmailConnection
from app.models.user import User
client = TestClient(app)


def _signup_and_login(email: str) -> str:
    signup = client.post(
        "/auth/signup",
        json={
            "name": "Gmail Status User",
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


def test_gmail_status_returns_connected_details() -> None:
    email = f"gmail-status-{uuid4()}@example.com"
    token = _signup_and_login(email)
    headers = {"Authorization": f"Bearer {token}"}

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        connection = GmailConnection(
            user_id=user.id,
            gmail_email="connected@example.com",
            access_token_encrypted="encrypted-access",
            refresh_token_encrypted="encrypted-refresh",
            token_uri="https://oauth2.googleapis.com/token",
            scopes="https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send",
            expiry=datetime.now(timezone.utc),
            connected_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            is_connected=True,
        )
        db.add(connection)
        db.commit()

        response = client.get("/gmail/status", headers=headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["is_connected"] is True
        assert payload["gmail_email"] == "connected@example.com"
        assert payload["can_send_replies"] is True
    finally:
        db.query(GmailConnection).filter(GmailConnection.user_id == user.id).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_gmail_disconnect_succeeds_with_existing_inactive_connection() -> None:
    email = f"gmail-disconnect-{uuid4()}@example.com"
    token = _signup_and_login(email)
    headers = {"Authorization": f"Bearer {token}"}

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        inactive_connection = GmailConnection(
            user_id=user.id,
            gmail_email="old@example.com",
            is_connected=False,
            connected_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        active_connection = GmailConnection(
            user_id=user.id,
            gmail_email="active@example.com",
            access_token_encrypted="encrypted-access",
            refresh_token_encrypted="encrypted-refresh",
            token_uri="https://oauth2.googleapis.com/token",
            scopes="https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send",
            expiry=datetime.now(timezone.utc),
            connected_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            is_connected=True,
        )
        db.add(inactive_connection)
        db.add(active_connection)
        db.commit()

        response = client.delete("/gmail/disconnect", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["message"] == "Gmail disconnected successfully"

        rows = db.query(GmailConnection).filter(GmailConnection.user_id == user.id).all()
        assert len(rows) == 2
        assert all(row.is_connected is False for row in rows)
    finally:
        db.query(GmailConnection).filter(GmailConnection.user_id == user.id).delete(synchronize_session=False)
        db.commit()
        db.close()
