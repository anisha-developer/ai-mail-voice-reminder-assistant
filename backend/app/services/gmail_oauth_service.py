from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, status
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.config import settings
from app.core.encryption import decrypt_value, encrypt_value
from app.core.redis_client import get_redis_client
from app.models.gmail_connection import GmailConnection
from app.models.user import User

STATE_TTL_SECONDS = 600
OAUTH_NONCE_PREFIX = "oauth_state_nonce:"


def _scopes() -> list[str]:
    return [scope for scope in settings.google_scopes.split() if scope.strip()]


def _state_secret() -> str:
    return settings.oauth_state_secret or settings.secret_key


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64url_decode(token: str) -> bytes:
    padding = "=" * (-len(token) % 4)
    return base64.urlsafe_b64decode((token + padding).encode())


def _oauth_flow(state: str | None = None) -> Flow:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google OAuth is not configured")
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uris": [settings.google_redirect_uri],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(client_config, scopes=_scopes(), state=state)
    flow.redirect_uri = settings.google_redirect_uri
    return flow


def build_state_token(user_id: int) -> str:
    nonce = secrets.token_urlsafe(16)
    payload = {
        "user_id": user_id,
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
        "nonce": nonce,
    }
    raw_payload = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    signature = hmac.new(_state_secret().encode(), raw_payload, hashlib.sha256).digest()
    try:
        redis_client = get_redis_client()
        redis_client.setex(
            f"{OAUTH_NONCE_PREFIX}{nonce}",
            STATE_TTL_SECONDS,
            json.dumps({"user_id": user_id, "code_verifier": None}),
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="OAuth replay protection store is unavailable") from exc
    return f"{_b64url_encode(raw_payload)}.{_b64url_encode(signature)}"


def _store_code_verifier(nonce: str, user_id: int, code_verifier: str) -> None:
    try:
        redis_client = get_redis_client()
        redis_client.setex(
            f"{OAUTH_NONCE_PREFIX}{nonce}",
            STATE_TTL_SECONDS,
            json.dumps({"user_id": user_id, "code_verifier": code_verifier}),
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="OAuth replay protection store is unavailable") from exc


def verify_state_token(state: str) -> dict[str, object]:
    try:
        payload_b64, signature_b64 = state.split(".", 1)
        raw_payload = _b64url_decode(payload_b64)
        provided_signature = _b64url_decode(signature_b64)
        expected_signature = hmac.new(_state_secret().encode(), raw_payload, hashlib.sha256).digest()
        if not hmac.compare_digest(expected_signature, provided_signature):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state signature")
        payload = json.loads(raw_payload.decode())
        if not isinstance(payload, dict):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state payload")
        if "user_id" not in payload or "timestamp" not in payload or "nonce" not in payload:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state payload")
        user_id = int(payload["user_id"])
        timestamp = int(payload["timestamp"])
        nonce = str(payload["nonce"])
        age = int(datetime.now(timezone.utc).timestamp()) - timestamp
        if age > STATE_TTL_SECONDS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state has expired")
        try:
            redis_client = get_redis_client()
            nonce_key = f"{OAUTH_NONCE_PREFIX}{nonce}"
            stored_user_id = redis_client.get(nonce_key)
            if stored_user_id is None:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state has expired or was already used")
            stored_payload = json.loads(stored_user_id)
            if not isinstance(stored_payload, dict):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state nonce")
            if str(stored_payload.get("user_id")) != str(user_id):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state nonce")
            redis_client.delete(nonce_key)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="OAuth replay protection store is unavailable") from exc
        return {
            "user_id": user_id,
            "timestamp": timestamp,
            "nonce": nonce,
            "code_verifier": stored_payload.get("code_verifier"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state") from exc


def create_authorization_url(user: User) -> tuple[str, str]:
    flow = _oauth_flow()
    state = build_state_token(user.id)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    nonce = json.loads(_b64url_decode(state.split(".", 1)[0]).decode())["nonce"]
    code_verifier = getattr(flow, "code_verifier", None)
    if code_verifier:
        _store_code_verifier(nonce, user.id, code_verifier)
    return auth_url, state


def _get_active_connection(db: Session, user_id: int) -> GmailConnection | None:
    return (
        db.query(GmailConnection)
        .filter(GmailConnection.user_id == user_id, GmailConnection.is_connected.is_(True))
        .first()
    )


def store_tokens_from_callback(db: Session, state: str, code: str) -> GmailConnection:
    state_payload = verify_state_token(state)
    user_id = int(state_payload["user_id"])
    flow = _oauth_flow(state=state)
    code_verifier = state_payload.get("code_verifier")
    if code_verifier:
        flow.fetch_token(code=code, code_verifier=code_verifier)
    else:
        flow.fetch_token(code=code)
    credentials: Credentials = flow.credentials

    if db.query(User).filter(User.id == user_id).first() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    gmail_email = None
    gmail_service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    profile = gmail_service.users().getProfile(userId="me").execute()
    gmail_email = profile.get("emailAddress")

    existing = _get_active_connection(db, user_id) or GmailConnection(user_id=user_id, is_connected=True)
    now = datetime.now(timezone.utc)
    existing.gmail_email = gmail_email
    existing.access_token_encrypted = encrypt_value(credentials.token or "")
    existing.refresh_token_encrypted = encrypt_value(credentials.refresh_token or "") if credentials.refresh_token else existing.refresh_token_encrypted
    existing.token_uri = credentials.token_uri
    existing.scopes = " ".join(credentials.scopes or _scopes())
    existing.expiry = credentials.expiry
    existing.connected_at = existing.connected_at or now
    existing.updated_at = now
    existing.is_connected = True
    db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def get_status(db: Session, user_id: int) -> GmailConnection | None:
    return _get_active_connection(db, user_id)


def can_send_replies(db: Session, user_id: int) -> bool:
    connection = _get_active_connection(db, user_id)
    if connection is None or not connection.refresh_token_encrypted or not connection.is_connected:
        return False
    scopes = set(connection.scopes.split() if connection.scopes else _scopes())
    return "https://www.googleapis.com/auth/gmail.send" in scopes


def disconnect(db: Session, user_id: int) -> None:
    existing = _get_active_connection(db, user_id)
    if existing is None:
        return
    existing.is_connected = False
    existing.access_token_encrypted = None
    existing.refresh_token_encrypted = None
    existing.updated_at = datetime.now(timezone.utc)
    db.add(existing)
    db.commit()


def get_connection_credentials(db: Session, user_id: int) -> Credentials | None:
    connection = _get_active_connection(db, user_id)
    if connection is None or not connection.refresh_token_encrypted:
        return None
    creds = Credentials(
        token=decrypt_value(connection.access_token_encrypted) if connection.access_token_encrypted else None,
        refresh_token=decrypt_value(connection.refresh_token_encrypted),
        token_uri=connection.token_uri,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=connection.scopes.split() if connection.scopes else _scopes(),
    )
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail connection expired. Please reconnect Gmail.") from exc
        connection.access_token_encrypted = encrypt_value(creds.token or "")
        connection.expiry = creds.expiry
        connection.updated_at = datetime.now(timezone.utc)
        db.add(connection)
        db.commit()
    return creds


def refresh_access_token_if_needed(db: Session, user_id: int) -> Credentials | None:
    connection = _get_active_connection(db, user_id)
    if connection is None or not connection.refresh_token_encrypted:
        return None
    refresh_token = decrypt_value(connection.refresh_token_encrypted)
    creds = Credentials(
        token=decrypt_value(connection.access_token_encrypted) if connection.access_token_encrypted else None,
        refresh_token=refresh_token,
        token_uri=connection.token_uri,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=connection.scopes.split() if connection.scopes else _scopes(),
    )
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail connection expired. Please reconnect Gmail.") from exc
        connection.access_token_encrypted = encrypt_value(creds.token or "")
        connection.expiry = creds.expiry
        connection.updated_at = datetime.now(timezone.utc)
        db.add(connection)
        db.commit()
    return creds
