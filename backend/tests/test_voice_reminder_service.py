from __future__ import annotations

import json
from datetime import date, datetime, timedelta, time, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.database.session import SessionLocal
from app.main import app
from app.models.email_message import EmailMessage
from app.models.email_summary import EmailSummary
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.reminder import Reminder
from app.models.user import User
from app.models.voice_call_interaction import VoiceCallInteraction
from app.models.voice_reminder_session import VoiceReminderSession
from app.services import voice_call_service
from app.services.voice_intent_service import INTENT_CONFIRM_CREATE_REMINDER, INTENT_START_REMINDER_CREATE, parse_voice_intent
from app.services.voice_reminder_service import parse_reminder_datetime, process_reminder_session_webhook, send_reminder_creation, start_reminder_session


client = TestClient(app)


def _login_token() -> str:
    response = client.post("/auth/login", json={"email": "browsertest@example.com", "password": "Test@12345"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _create_reminder_voice_test_call() -> tuple[int, list[int], list[int]]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        assert user is not None
        message_ids: list[int] = []
        summary_ids: list[int] = []
        for index in range(1, 3):
            message = EmailMessage(
                user_id=user.id,
                gmail_message_id=f"reminder-phase14-{uuid4()}",
                gmail_thread_id=None,
                sender=f"sender{index}@example.com",
                recipient=user.email,
                subject=f"Reminder Test Email {index}",
                snippet=f"Snippet {index}",
                plain_body=f"Body {index}",
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
            message_ids.append(message.id)
            summary = EmailSummary(
                user_id=user.id,
                email_message_id=message.id,
                sender=message.sender,
                subject=message.subject,
                short_summary=f"Short summary {index}",
                detailed_summary=f"Detailed summary {index}",
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
            summary_ids.append(summary.id)

        call_log = MailSummaryCallLog(
            user_id=user.id,
            call_type="mail_summary",
            call_status="prepared",
            call_date=date.today(),
            call_time=time(9, 0),
            summary_count=len(summary_ids),
            script_text="Test script",
            delivery_status="pending",
            delivered_summary_ids=json.dumps(summary_ids),
            failure_reason=None,
            provider="twilio",
            provider_call_id="CA-test-phase14",
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
        db.refresh(call_log)
        return call_log.id, summary_ids, message_ids
    finally:
        db.close()


def _cleanup_reminder_voice_test_call(call_log_id: int, summary_ids: list[int], message_ids: list[int]) -> None:
    db = SessionLocal()
    try:
        linked_reminder_ids = [
            row[0]
            for row in db.query(VoiceReminderSession.created_reminder_id)
            .filter(
                VoiceReminderSession.mail_call_log_id == call_log_id,
                VoiceReminderSession.created_reminder_id.is_not(None),
            )
            .all()
        ]
        db.query(VoiceCallInteraction).filter(VoiceCallInteraction.mail_call_log_id == call_log_id).delete(synchronize_session=False)
        db.query(VoiceReminderSession).filter(VoiceReminderSession.mail_call_log_id == call_log_id).delete(synchronize_session=False)
        db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).delete(synchronize_session=False)
        db.query(EmailSummary).filter(EmailSummary.id.in_(summary_ids)).delete(synchronize_session=False)
        db.query(EmailMessage).filter(EmailMessage.id.in_(message_ids)).delete(synchronize_session=False)
        if linked_reminder_ids:
            db.query(Reminder).filter(Reminder.id.in_(linked_reminder_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_reminder_intent_parser() -> None:
    parsed = parse_voice_intent("remind me about email number 1 tomorrow at 3 pm")
    assert parsed.intent == INTENT_START_REMINDER_CREATE

    confirm = parse_voice_intent("yes")
    assert confirm.intent in {INTENT_CONFIRM_CREATE_REMINDER, "CONFIRM_SEND_REPLY"}


def test_reminder_datetime_parser() -> None:
    parsed = parse_reminder_datetime("2026-06-06T15:00:00+00:00")
    assert parsed is not None
    assert parsed.tzinfo is not None


def test_voice_reminder_confirmation_flow() -> None:
    token = _login_token()
    call_log_id, summary_ids, message_ids = _create_reminder_voice_test_call()
    try:
        headers = {"Authorization": f"Bearer {token}"}
        db = SessionLocal()
        try:
            VoiceReminderSession.__table__.create(bind=db.get_bind(), checkfirst=True)
            user = db.query(User).filter(User.email == "browsertest@example.com").first()
            call_log = db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).first()
            assert user is not None and call_log is not None
            summary = db.query(EmailSummary).filter(EmailSummary.id == summary_ids[0]).first()
            assert summary is not None
            session = start_reminder_session(
                db,
                user,
                call_log,
                summary,
                target_email_reference=1,
                reminder_datetime=datetime.now(timezone.utc) + timedelta(hours=2),
            )
            assert session.status == "awaiting_confirmation"
        finally:
            db.close()

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(voice_call_service, "get_active_reminder_session", lambda *args, **kwargs: session)
        response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "yes", "Confidence": "0.98", "CallSid": "CA-test-phase14"},
        )
        monkeypatch.undo()
        assert response.status_code == 200, response.text
        assert "reminder has been created" in response.text.lower()

        interactions = client.get(f"/voice/mail-calls/{call_log_id}/interactions", headers=headers)
        assert interactions.status_code == 200
    finally:
        _cleanup_reminder_voice_test_call(call_log_id, summary_ids, message_ids)


def test_voice_reminder_past_time_confirmation_prompts_for_new_time() -> None:
    call_log_id, summary_ids, message_ids = _create_reminder_voice_test_call()
    try:
        db = SessionLocal()
        try:
            VoiceReminderSession.__table__.create(bind=db.get_bind(), checkfirst=True)
            user = db.query(User).filter(User.email == "browsertest@example.com").first()
            call_log = db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).first()
            assert user is not None and call_log is not None
            summary = db.query(EmailSummary).filter(EmailSummary.id == summary_ids[0]).first()
            assert summary is not None
            before_count = db.query(Reminder).filter(Reminder.user_id == user.id, Reminder.title.like("Check email:%")).count()
            past_session = start_reminder_session(
                db,
                user,
                call_log,
                summary,
                target_email_reference=1,
                reminder_datetime=datetime.now(timezone.utc) - timedelta(minutes=5),
            )
            assert past_session.status == "awaiting_confirmation"
            result = process_reminder_session_webhook(
                db,
                call_log,
                past_session,
                "yes save it",
                "0.98",
                parse_voice_intent("yes save it"),
            )
            assert "future time" in result.lower()

            refreshed = db.query(VoiceReminderSession).filter(VoiceReminderSession.id == past_session.id).first()
            assert refreshed is not None
            assert refreshed.status == "awaiting_details"
            assert refreshed.last_error == "Reminder time must be in the future"
            assert refreshed.created_reminder_id is None
            after_count = db.query(Reminder).filter(Reminder.user_id == user.id, Reminder.title.like("Check email:%")).count()
            assert after_count == before_count
        finally:
            db.close()
    finally:
        _cleanup_reminder_voice_test_call(call_log_id, summary_ids, message_ids)


def test_voice_reminder_creation_is_idempotent_for_same_session() -> None:
    call_log_id, summary_ids, message_ids = _create_reminder_voice_test_call()
    try:
        db = SessionLocal()
        try:
            VoiceReminderSession.__table__.create(bind=db.get_bind(), checkfirst=True)
            user = db.query(User).filter(User.email == "browsertest@example.com").first()
            call_log = db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).first()
            summary = db.query(EmailSummary).filter(EmailSummary.id == summary_ids[0]).first()
            assert user is not None and call_log is not None and summary is not None
            session = start_reminder_session(
                db,
                user,
                call_log,
                summary,
                target_email_reference=1,
                reminder_datetime=datetime.now(timezone.utc) + timedelta(minutes=10),
            )
            created_one = send_reminder_creation(db, user, session)
            created_two = send_reminder_creation(db, user, session)
            assert created_one.id == created_two.id
            matches = (
                db.query(Reminder)
                .filter(Reminder.user_id == user.id, Reminder.title == created_one.title, Reminder.reminder_at == created_one.reminder_at)
                .all()
            )
            assert len(matches) == 1
        finally:
            db.close()
    finally:
        _cleanup_reminder_voice_test_call(call_log_id, summary_ids, message_ids)
