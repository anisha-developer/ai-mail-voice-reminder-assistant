from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.database.session import SessionLocal
from app.models.email_message import EmailMessage
from app.models.user import User
from app.services.gmail_email_service import get_sync_status, list_user_emails, sync_user_emails


def _get_user(email: str = "browsertest@example.com") -> User:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        db.expunge(user)
        return user
    finally:
        db.close()


class _FakeMessagesResource:
    def __init__(self, snapshot_messages: list[dict[str, str]], full_messages: dict[str, dict[str, object]]):
        self.snapshot_messages = snapshot_messages
        self.full_messages = full_messages

    def list(self, userId: str, labelIds: list[str], maxResults: int, pageToken: str | None = None):  # noqa: N803
        class _Response:
            def __init__(self, payload):
                self.payload = payload

            def execute(self):
                return self.payload

        return _Response({"messages": self.snapshot_messages, "nextPageToken": None})

    def get(self, userId: str, id: str, format: str):  # noqa: A002, N803
        class _Response:
            def __init__(self, payload):
                self.payload = payload

            def execute(self):
                return self.payload

        return _Response(self.full_messages[id])


class _FakeUsersResource:
    def __init__(self, messages_resource):
        self._messages_resource = messages_resource

    def messages(self):
        return self._messages_resource


class _FakeGmailService:
    def __init__(self, snapshot_messages: list[dict[str, str]], full_messages: dict[str, dict[str, object]]):
        self._messages_resource = _FakeMessagesResource(snapshot_messages, full_messages)

    def users(self):
        return _FakeUsersResource(self._messages_resource)


def test_sync_reconciles_deleted_inbox_messages_and_counts_active_only(monkeypatch) -> None:
    user = _get_user()
    active_gmail_id = f"sync-active-{uuid4()}"
    stale_gmail_id = f"sync-stale-{uuid4()}"
    new_gmail_id = f"sync-new-{uuid4()}"
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    try:
        active_email = EmailMessage(
            user_id=user.id,
            gmail_message_id=active_gmail_id,
            gmail_thread_id=f"thread-{uuid4()}",
            sender="Active Sender <active@example.com>",
            recipient=user.email,
            subject="Active inbox email",
            snippet="Active inbox email",
            plain_body="Active inbox email",
            received_at=now,
            has_attachments=False,
            is_read_from_gmail=True,
            is_summarized=False,
            is_in_inbox=True,
            updated_at=now,
        )
        stale_email = EmailMessage(
            user_id=user.id,
            gmail_message_id=stale_gmail_id,
            gmail_thread_id=f"thread-{uuid4()}",
            sender="Stale Sender <stale@example.com>",
            recipient=user.email,
            subject="Stale inbox email",
            snippet="Stale inbox email",
            plain_body="Stale inbox email",
            received_at=now,
            has_attachments=False,
            is_read_from_gmail=True,
            is_summarized=False,
            is_in_inbox=True,
            updated_at=now,
        )
        db.add(active_email)
        db.add(stale_email)
        db.commit()

        snapshot_messages = [{"id": active_gmail_id}, {"id": new_gmail_id}]
        full_messages = {
            new_gmail_id: {
                "threadId": f"thread-{uuid4()}",
                "internalDate": str(int(now.timestamp() * 1000)),
                "snippet": "New inbox email",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "New Sender <new@example.com>"},
                        {"name": "To", "value": user.email},
                        {"name": "Subject", "value": "New inbox email"},
                    ],
                    "parts": [],
                },
                "labelIds": ["INBOX"],
            }
        }
        fake_service = _FakeGmailService(snapshot_messages, full_messages)
        monkeypatch.setattr(
            "app.services.gmail_email_service._gmail_service_for_user",
            lambda *_args, **_kwargs: (fake_service, None),
        )

        result = sync_user_emails(db, user, max_results=50, max_pages=1)
        assert result["synced_count"] == 1
        assert result["gmail_returned_count"] == 2

        active_record = db.query(EmailMessage).filter(EmailMessage.user_id == user.id, EmailMessage.gmail_message_id == active_gmail_id).first()
        stale_record = db.query(EmailMessage).filter(EmailMessage.user_id == user.id, EmailMessage.gmail_message_id == stale_gmail_id).first()
        new_record = db.query(EmailMessage).filter(EmailMessage.user_id == user.id, EmailMessage.gmail_message_id == new_gmail_id).first()

        assert active_record is not None and active_record.is_in_inbox is True
        assert stale_record is not None and stale_record.is_in_inbox is False
        assert new_record is not None and new_record.is_in_inbox is True

        sync_status = get_sync_status(db, user.id)
        assert sync_status["total_emails_stored"] == 2

        items, total = list_user_emails(db, user.id, page=1, limit=20)
        assert total == 2
        assert {item.gmail_message_id for item in items} == {active_gmail_id, new_gmail_id}
        assert stale_gmail_id not in {item.gmail_message_id for item in items}
    finally:
        db.query(EmailMessage).filter(
            EmailMessage.user_id == user.id,
            EmailMessage.gmail_message_id.in_([active_gmail_id, stale_gmail_id, new_gmail_id]),
        ).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_sync_status_uses_live_gmail_inbox_count_not_local_subset(monkeypatch) -> None:
    user = _get_user()
    local_gmail_id = f"sync-local-{uuid4()}"
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    try:
        local_email = EmailMessage(
            user_id=user.id,
            gmail_message_id=local_gmail_id,
            gmail_thread_id=f"thread-{uuid4()}",
            sender="Local Sender <local@example.com>",
            recipient=user.email,
            subject="Local inbox email",
            snippet="Local inbox email",
            plain_body="Local inbox email",
            received_at=now,
            has_attachments=False,
            is_read_from_gmail=True,
            is_summarized=False,
            is_in_inbox=True,
            updated_at=now,
        )
        db.add(local_email)
        db.commit()

        snapshot_messages = [{"id": f"snapshot-{index}"} for index in range(305)]
        full_messages = {
            snapshot_messages[0]["id"]: {
                "threadId": f"thread-{uuid4()}",
                "internalDate": str(int(now.timestamp() * 1000)),
                "snippet": "Newest inbox email",
                "payload": {"headers": [], "parts": []},
                "labelIds": ["INBOX"],
            }
        }
        fake_service = _FakeGmailService(snapshot_messages, full_messages)
        monkeypatch.setattr(
            "app.services.gmail_email_service._gmail_service_for_user",
            lambda *_args, **_kwargs: (fake_service, None),
        )

        sync_status = get_sync_status(db, user.id)
        assert sync_status["total_emails_stored"] == 305
        assert sync_status["gmail_connected"] is True
    finally:
        db.query(EmailMessage).filter(
            EmailMessage.user_id == user.id,
            EmailMessage.gmail_message_id == local_gmail_id,
        ).delete(synchronize_session=False)
        db.commit()
        db.close()
