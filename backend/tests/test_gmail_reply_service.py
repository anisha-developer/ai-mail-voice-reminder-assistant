from __future__ import annotations

from datetime import datetime, timezone, date, time
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.database.session import SessionLocal
from app.models.email_message import EmailMessage
from app.models.email_reply_action import EmailReplyAction
from app.models.email_summary import EmailSummary
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.user import User
from app.models.voice_call_interaction import VoiceCallInteraction
from app.models.voice_reply_session import VoiceReplySession
from app.models.voice_reminder_session import VoiceReminderSession
from app.services import gmail_reply_service


class _FakeSendResult:
    def __init__(self, message_id: str = "msg-123") -> None:
        self._message_id = message_id

    def execute(self) -> dict[str, str]:
        return {"id": self._message_id}


class _FakeMessages:
    def send(self, **_kwargs):
        return _FakeSendResult()


class _FakeUsers:
    def messages(self):
        return _FakeMessages()


class _FakeGmailService:
    def users(self):
        return _FakeUsers()


@pytest.fixture()
def reply_test_data():
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        assert user is not None

        message = EmailMessage(
            user_id=user.id,
            gmail_message_id=f"reply-test-{uuid4()}",
            gmail_thread_id=f"thread-{uuid4()}",
            sender="sender@example.com",
            recipient=user.email,
            subject="Reply test email",
            snippet="Reply test snippet",
            plain_body="Reply test body",
            html_body=None,
            received_at=datetime.now(timezone.utc),
            has_attachments=False,
            attachment_metadata=None,
            is_read_from_gmail=True,
            is_summarized=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(message)
        db.flush()

        summary = EmailSummary(
            user_id=user.id,
            email_message_id=message.id,
            sender=message.sender,
            subject=message.subject,
            short_summary="Short summary",
            detailed_summary="Detailed summary",
            action_required_text=None,
            attachment_note=None,
            summary_status="completed",
            error_message=None,
            is_delivered_in_mail_call=False,
            delivered_at=None,
            mail_call_log_id=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(summary)
        db.flush()

        call_log = MailSummaryCallLog(
            user_id=user.id,
            call_type="mail_summary",
            call_status="prepared",
            call_date=date.today(),
            call_time=time(9, 0),
            summary_count=1,
            script_text="Test script",
            delivery_status="pending",
            delivered_summary_ids="[]",
            failure_reason=None,
            provider="twilio",
            provider_call_id=f"CA-{uuid4()}",
            to_phone_number=user.phone_number,
            from_phone_number="+17154196839",
            call_started_at=None,
            call_completed_at=None,
            call_duration_seconds=None,
            provider_status="in-progress",
            provider_error_message=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(call_log)
        db.commit()
        db.refresh(message)
        db.refresh(summary)
        db.refresh(call_log)
        yield {
            "user_id": user.id,
            "message_id": message.id,
            "summary_id": summary.id,
            "call_log_id": call_log.id,
            "thread_id": message.gmail_thread_id,
        }
    finally:
        db.execute(text("DELETE FROM voice_reminder_sessions"))
        db.execute(text("DELETE FROM voice_call_interactions"))
        db.execute(text("DELETE FROM email_reply_actions"))
        db.execute(text("DELETE FROM voice_reply_sessions"))
        db.execute(text("DELETE FROM mail_summary_call_logs WHERE call_type = 'mail_summary' AND script_text = 'Test script'"))
        db.execute(text("DELETE FROM email_summaries WHERE short_summary = 'Short summary'"))
        db.execute(text("DELETE FROM email_messages WHERE gmail_message_id LIKE 'reply-test-%'"))
        db.commit()
        db.close()


def test_reply_session_lifecycle_and_send_requires_confirmation(monkeypatch: pytest.MonkeyPatch, reply_test_data) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == reply_test_data["user_id"]).first()
        call_log = db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == reply_test_data["call_log_id"]).first()
        summary = db.query(EmailSummary).filter(EmailSummary.id == reply_test_data["summary_id"]).first()
        assert user is not None and call_log is not None and summary is not None

        session = gmail_reply_service.start_reply_session(db, user, call_log, summary)
        assert session.status == "awaiting_body"

        monkeypatch.setattr(gmail_reply_service, "build", lambda *args, **kwargs: _FakeGmailService())
        monkeypatch.setattr(
            gmail_reply_service,
            "get_connection_credentials",
            lambda _db, _user_id: SimpleNamespace(
                refresh_token="refresh-token",
                token="access-token",
                token_uri="https://oauth2.googleapis.com/token",
                scopes=["https://www.googleapis.com/auth/gmail.send"],
                expired=False,
            ),
        )

        with pytest.raises(HTTPException):
            gmail_reply_service.send_reply(db, user, session)

        updated = gmail_reply_service.update_reply_body(db, session, "I will reply tomorrow.")
        assert updated.status == "awaiting_confirmation"
        assert updated.reply_body == "I will reply tomorrow."

        session = db.query(VoiceReplySession).filter(VoiceReplySession.id == updated.id).first()
        assert session is not None
        assert session.status == "awaiting_confirmation"

        result = gmail_reply_service.send_reply(db, user, session)
        assert result["provider_message_id"] == "msg-123"

        reloaded = db.query(VoiceReplySession).filter(VoiceReplySession.id == session.id).first()
        assert reloaded is not None
        assert reloaded.status == "sent"

        actions = db.query(EmailReplyAction).filter(EmailReplyAction.voice_reply_session_id == session.id).all()
        assert len(actions) == 1
        assert actions[0].status == "sent"
    finally:
        db.query(EmailReplyAction).filter(EmailReplyAction.voice_reply_session_id.isnot(None)).delete(synchronize_session=False)
        db.query(VoiceReplySession).delete(synchronize_session=False)
        db.query(MailSummaryCallLog).filter(MailSummaryCallLog.script_text == "Test script").delete(synchronize_session=False)
        db.query(EmailSummary).filter(EmailSummary.short_summary == "Short summary").delete(synchronize_session=False)
        db.query(EmailMessage).filter(EmailMessage.gmail_message_id.like("reply-test-%")).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_reply_send_blocks_other_user(monkeypatch: pytest.MonkeyPatch, reply_test_data) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == reply_test_data["user_id"]).first()
        call_log = db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == reply_test_data["call_log_id"]).first()
        summary = db.query(EmailSummary).filter(EmailSummary.id == reply_test_data["summary_id"]).first()
        assert user is not None and call_log is not None and summary is not None

        session = gmail_reply_service.start_reply_session(db, user, call_log, summary, reply_body="Please reply")
        other_user = User(
            name="Other User",
            email=f"other-{uuid4()}@example.com",
            phone_number="+919999999998",
            timezone="UTC",
            preferred_language="English",
            hashed_password="hash",
            is_active=True,
            is_verified=False,
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)

        with pytest.raises(HTTPException):
            gmail_reply_service.send_reply(db, other_user, session)
    finally:
        db.execute(text("DELETE FROM voice_reminder_sessions"))
        db.execute(text("DELETE FROM voice_call_interactions"))
        db.execute(text("DELETE FROM email_reply_actions"))
        db.execute(text("DELETE FROM voice_reply_sessions"))
        db.execute(text("DELETE FROM mail_summary_call_logs WHERE call_type = 'mail_summary' AND script_text = 'Test script'"))
        db.execute(text("DELETE FROM email_summaries WHERE short_summary = 'Short summary'"))
        db.execute(text("DELETE FROM email_messages WHERE gmail_message_id LIKE 'reply-test-%'"))
        db.execute(text("DELETE FROM users WHERE email LIKE 'other-%@example.com'"))
        db.commit()
        db.close()
