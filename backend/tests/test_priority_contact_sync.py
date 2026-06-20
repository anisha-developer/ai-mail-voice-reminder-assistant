from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.database.session import Base, SessionLocal, engine
from app.models.email_message import EmailMessage
from app.models.email_summary import EmailSummary
from app.models.gmail_connection import GmailConnection
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.priority_contact import PriorityContact
from app.models.priority_mail_alert_log import PriorityMailAlertLog
from app.models.user import User
from app.models.user_call_preference import UserCallPreference
from app.services import priority_contact_service as pcs
from app.services.gmail_email_service import sync_user_emails


Base.metadata.create_all(bind=engine)


class _FakeMessageCall:
    def __init__(self, payload: dict[str, object]):
        self._payload = payload

    def execute(self):
        return self._payload


class _FakeMessagesAPI:
    def __init__(self, messages: list[dict[str, str]], full_message: dict[str, object]):
        self._messages = messages
        self._full_message = full_message

    def list(self, **kwargs):
        return _FakeMessageCall({"messages": self._messages, "nextPageToken": None})

    def get(self, **kwargs):
        return _FakeMessageCall(self._full_message)


class _FakeUsersAPI:
    def __init__(self, messages: list[dict[str, str]], full_message: dict[str, object]):
        self._messages = messages
        self._full_message = full_message

    def messages(self):
        return _FakeMessagesAPI(self._messages, self._full_message)


class _FakeGmailService:
    def __init__(self, messages: list[dict[str, str]], full_message: dict[str, object]):
        self._messages = messages
        self._full_message = full_message

    def users(self):
        return _FakeUsersAPI(self._messages, self._full_message)


def _create_user() -> tuple[int, str]:
    db = SessionLocal()
    try:
        email = f"priority-sync-{uuid4()}@example.com"
        user = User(
            email=email,
            name="Priority Sync User",
            phone_number="+919843731545",
            timezone="Asia/Kolkata",
            preferred_language="English",
            hashed_password="hash",
            is_active=True,
            is_verified=True,
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.add(
            GmailConnection(
                user_id=user.id,
                gmail_email=email,
                access_token_encrypted="encrypted-access",
                refresh_token_encrypted="encrypted-refresh",
                token_uri="https://oauth2.googleapis.com/token",
                scopes="scope",
                expiry=datetime.now(timezone.utc) + timedelta(hours=1),
                is_connected=True,
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            UserCallPreference(
                user_id=user.id,
                phone_number="+919843731545",
                timezone="Asia/Kolkata",
                call_slot_1_time="09:00",
                call_slot_1_enabled=True,
                call_slot_2_time="13:00",
                call_slot_2_enabled=False,
                call_slot_3_time="19:00",
                call_slot_3_enabled=False,
                minimum_new_emails_to_call=1,
                skip_if_no_new_emails=True,
                avoid_repeating_delivered_emails=True,
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        return user.id, email
    finally:
        db.close()


def _cleanup_user(user_id: int) -> None:
    db = SessionLocal()
    try:
        db.query(PriorityMailAlertLog).filter(PriorityMailAlertLog.user_id == user_id).delete(synchronize_session=False)
        db.query(PriorityContact).filter(PriorityContact.user_id == user_id).delete(synchronize_session=False)
        db.query(EmailSummary).filter(EmailSummary.user_id == user_id).delete(synchronize_session=False)
        db.query(MailSummaryCallLog).filter(MailSummaryCallLog.user_id == user_id).delete(synchronize_session=False)
        db.query(EmailMessage).filter(EmailMessage.user_id == user_id).delete(synchronize_session=False)
        db.query(UserCallPreference).filter(UserCallPreference.user_id == user_id).delete(synchronize_session=False)
        db.query(GmailConnection).filter(GmailConnection.user_id == user_id).delete(synchronize_session=False)
        db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _patch_priority_hooks(monkeypatch, call_results: list[dict[str, object]]) -> None:
    def fake_start_mail_summary_voice_call(db, user, call_log_id, call_purpose="daily_mail_summary"):
        call_results.append({"call_log_id": call_log_id, "call_purpose": call_purpose, "user_id": user.id})
        return {"call_log_id": call_log_id, "provider": "make", "status": "queued", "provider_call_id": f"fake-{call_log_id}", "call_status": "queued"}

    def fake_summarize_email_ids(db, user, email_ids):
        email_id = email_ids[0]
        email = db.query(EmailMessage).filter(EmailMessage.id == email_id, EmailMessage.user_id == user.id).first()
        assert email is not None
        summary = EmailSummary(
            user_id=user.id,
            email_message_id=email.id,
            sender=email.sender,
            subject=email.subject,
            short_summary="Email received about a priority message. It may need review.",
            detailed_summary="Email received about a priority message. It may need review.",
            action_required_text="Review this email.",
            summary_status="completed",
            updated_at=datetime.now(timezone.utc),
        )
        db.add(summary)
        db.commit()
        return {"processed_count": 1, "success_count": 1, "failed_count": 0}

    monkeypatch.setattr(pcs, "start_mail_summary_voice_call", fake_start_mail_summary_voice_call)
    monkeypatch.setattr(pcs, "summarize_email_ids", fake_summarize_email_ids)


def test_priority_sender_triggers_one_immediate_call(monkeypatch) -> None:
    user_id, _ = _create_user()
    db = SessionLocal()
    call_results: list[dict[str, object]] = []
    try:
        user = db.query(User).filter(User.id == user_id).first()
        assert user is not None
        db.add(
            PriorityContact(
                user_id=user.id,
                display_name="Boss",
                email_address="boss@example.com",
                relationship="Manager",
                priority_level=1,
                notes=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

        _patch_priority_hooks(monkeypatch, call_results)

        fake_service = _FakeGmailService(
            messages=[{"id": "gmail-1"}],
            full_message={
                "id": "gmail-1",
                "threadId": "thread-1",
                "internalDate": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
                "snippet": "Please review this priority note.",
                "labelIds": ["INBOX"],
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Boss <boss@example.com>"},
                        {"name": "To", "value": "Priority User <user@example.com>"},
                        {"name": "Subject", "value": "Priority alert"},
                    ],
                    "mimeType": "multipart/mixed",
                    "parts": [],
                },
            },
        )

        monkeypatch.setattr(
            "app.services.gmail_email_service._gmail_service_for_user",
            lambda db, user_id: (fake_service, SimpleNamespace()),
        )

        result = sync_user_emails(db, user, max_results=1, max_pages=1)
        assert result["synced_count"] == 1
        assert result["skipped_duplicates"] == 0
        assert result["total_processed"] == 1
        assert len(call_results) == 1
        assert call_results[0]["call_purpose"] == "priority_contact_mail_alert"

        duplicate = pcs.process_priority_email_alert(
            db,
            user,
            db.query(EmailMessage).filter(EmailMessage.user_id == user.id, EmailMessage.gmail_message_id == "gmail-1").first(),
        )
        assert duplicate["status"] == "duplicate"
        assert len(call_results) == 1
        assert db.query(PriorityMailAlertLog).filter(PriorityMailAlertLog.user_id == user.id).count() == 1
    finally:
        db.close()
        _cleanup_user(user_id)


def test_non_priority_sender_does_not_trigger_call(monkeypatch) -> None:
    user_id, _ = _create_user()
    db = SessionLocal()
    call_results: list[dict[str, object]] = []
    try:
        user = db.query(User).filter(User.id == user_id).first()
        assert user is not None
        _patch_priority_hooks(monkeypatch, call_results)

        fake_service = _FakeGmailService(
            messages=[{"id": "gmail-2"}],
            full_message={
                "id": "gmail-2",
                "threadId": "thread-2",
                "internalDate": str(int(datetime.now(timezone.utc).timestamp() * 1000)),
                "snippet": "General inbox message.",
                "labelIds": ["INBOX"],
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Newsletters <news@example.com>"},
                        {"name": "To", "value": "Priority User <user@example.com>"},
                        {"name": "Subject", "value": "Weekly update"},
                    ],
                    "mimeType": "multipart/mixed",
                    "parts": [],
                },
            },
        )

        monkeypatch.setattr(
            "app.services.gmail_email_service._gmail_service_for_user",
            lambda db, user_id: (fake_service, SimpleNamespace()),
        )

        result = sync_user_emails(db, user, max_results=1, max_pages=1)
        assert result["synced_count"] == 1
        assert len(call_results) == 0
        assert db.query(PriorityMailAlertLog).filter(PriorityMailAlertLog.user_id == user.id).count() == 0
    finally:
        db.close()
        _cleanup_user(user_id)
