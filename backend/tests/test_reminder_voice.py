from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.database.session import SessionLocal
from app.main import app
from app.models.reminder import Reminder
from app.models.user import User
from app.services.reminder_service import process_twilio_reminder_status_callback
from app.services.reminder_voice_service import build_reminder_twiml


client = TestClient(app)


def _create_reminder(title: str, notes: str | None = "Some notes") -> int:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        assert user is not None
        reminder = Reminder(
            user_id=user.id,
            title=title,
            notes=notes,
            reminder_at=datetime.now(timezone.utc),
            timezone="UTC",
            phone_number="+919843731545",
            status="scheduled",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(reminder)
        db.commit()
        db.refresh(reminder)
        return reminder.id
    finally:
        db.close()


def _cleanup(title: str) -> None:
    db = SessionLocal()
    try:
        db.query(Reminder).filter(Reminder.title == title).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_reminder_twiml_and_status_callback() -> None:
    title = "Reminder Voice Test"
    reminder_id = _create_reminder(title, "Read the docs")
    try:
        twiml = build_reminder_twiml(Reminder(title=title, notes="Read the docs", reminder_at=datetime.now(timezone.utc), timezone="UTC", phone_number="+919843731545", status="scheduled", user_id=1))
        assert "Hello. This is your reminder." in twiml
        assert "Reminder: Reminder Voice Test." in twiml
        assert "Notes: Read the docs." in twiml
        assert "Goodbye" in twiml

        db = SessionLocal()
        try:
            reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
            assert reminder is not None
            process_twilio_reminder_status_callback(db, reminder_id=reminder.id, call_sid="CA-test-1", call_status="completed")
            reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
            assert reminder is not None
            assert reminder.status == "completed"
            assert reminder.provider_call_id == "CA-test-1"
            assert reminder.called_at is not None
            assert reminder.last_error is None

            process_twilio_reminder_status_callback(db, reminder_id=reminder.id, call_sid="CA-test-2", call_status="busy")
            reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
            assert reminder is not None
            assert reminder.status in {"retry_scheduled", "missed"}
            assert reminder.retry_count == 1
            assert reminder.last_call_status == "busy"
            assert reminder.next_retry_at is not None or reminder.status == "missed"
        finally:
            db.close()
    finally:
        _cleanup(title)


def test_reminder_twiml_without_notes_and_fallback() -> None:
    title = "Reminder Voice No Notes"
    reminder_id = _create_reminder(title, None)
    try:
        db = SessionLocal()
        try:
            reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
            assert reminder is not None
            twiml = build_reminder_twiml(reminder)
            assert "Reminder: Reminder Voice No Notes." in twiml
            assert "Notes:" not in twiml
        finally:
            db.close()

        missing = client.get("/voice/reminders/999999/twiml")
        assert missing.status_code == 200
        assert "could not find that reminder" in missing.text.lower()
    finally:
        _cleanup(title)
