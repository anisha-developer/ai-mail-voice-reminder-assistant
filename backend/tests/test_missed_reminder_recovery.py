from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from app.database.session import SessionLocal
from app.config import settings
from app.main import app
from app.models.reminder import Reminder
from app.models.user import User
from app.services import reminder_service
from app.services.reminder_service import process_twilio_reminder_status_callback


client = TestClient(app)


def _login() -> str:
    response = client.post("/auth/login", json={"email": "browsertest@example.com", "password": "Test@12345"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {_login()}"}


def _create_reminder(title: str, status: str = "scheduled", offset_minutes: int = 5) -> int:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        assert user is not None
        reminder_at = datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(minutes=offset_minutes)
        reminder = Reminder(
            user_id=user.id,
            title=title,
            notes="Recovery test reminder",
            reminder_at=reminder_at.astimezone(timezone.utc),
            timezone="Asia/Kolkata",
            phone_number="+919843731545",
            status=status,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(reminder)
        db.commit()
        db.refresh(reminder)
        return reminder.id
    finally:
        db.close()


def _delete_reminder(reminder_id: int) -> None:
    db = SessionLocal()
    try:
        db.query(Reminder).filter(Reminder.id == reminder_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_no_answer_schedules_retry() -> None:
    reminder_id = _create_reminder("Retry callback no-answer")
    try:
        db = SessionLocal()
        try:
            process_twilio_reminder_status_callback(db, reminder_id=reminder_id, call_sid="CA-no-answer", call_status="no-answer")
            reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
            assert reminder is not None
            assert reminder.status == "retry_scheduled"
            assert reminder.retry_count == 1
            assert reminder.last_call_status == "no_answer"
            assert reminder.next_retry_at is not None
        finally:
            db.close()
    finally:
        _delete_reminder(reminder_id)


def test_busy_failed_canceled_schedule_retry() -> None:
    for status in ["busy", "failed", "canceled"]:
        reminder_id = _create_reminder(f"Retry callback {status}")
        try:
            db = SessionLocal()
            try:
                process_twilio_reminder_status_callback(db, reminder_id=reminder_id, call_sid=f"CA-{status}", call_status=status)
                reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
                assert reminder is not None
                assert reminder.status == "retry_scheduled"
                assert reminder.retry_count == 1
                assert reminder.last_call_status == status.replace("-", "_")
                assert reminder.next_retry_at is not None
            finally:
                db.close()
        finally:
            _delete_reminder(reminder_id)


def test_max_retries_exhausted_becomes_missed() -> None:
    reminder_id = _create_reminder("Retry max exhausted")
    try:
        db = SessionLocal()
        try:
            reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
            assert reminder is not None
            reminder.retry_count = 2
            reminder.max_retry_attempts = 3
            db.add(reminder)
            db.commit()

            process_twilio_reminder_status_callback(db, reminder_id=reminder_id, call_sid="CA-final", call_status="no-answer")
            reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
            assert reminder is not None
            assert reminder.status == "missed"
            assert reminder.next_retry_at is None
            assert reminder.last_error == "missed after max retry attempts"
        finally:
            db.close()
    finally:
        _delete_reminder(reminder_id)


def test_completed_callback_stops_retries() -> None:
    reminder_id = _create_reminder("Retry completed callback")
    try:
        db = SessionLocal()
        try:
            process_twilio_reminder_status_callback(db, reminder_id=reminder_id, call_sid="CA-complete", call_status="completed")
            reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
            assert reminder is not None
            assert reminder.status == "completed"
            assert reminder.next_retry_at is None
            assert reminder.last_error is None
        finally:
            db.close()
    finally:
        _delete_reminder(reminder_id)


def test_scheduler_picks_retry_and_snoozed(monkeypatch) -> None:
    retry_id = _create_reminder("Retry scheduled due", status="retry_scheduled", offset_minutes=5)
    snooze_id = _create_reminder("Snoozed due", status="snoozed", offset_minutes=5)
    calls: list[int] = []

    def fake_start(db, reminder, user):
        calls.append(reminder.id)
        reminder.provider_call_id = f"CA-{reminder.id}"
        reminder.status = "calling"
        reminder.called_at = datetime.now(timezone.utc)
        reminder.updated_at = datetime.now(timezone.utc)
        db.add(reminder)
        db.commit()

    monkeypatch.setattr(reminder_service, "start_reminder_call", fake_start)
    monkeypatch.setattr(settings, "reminder_calls_enabled", True)

    db = SessionLocal()
    try:
        retry = db.query(Reminder).filter(Reminder.id == retry_id).first()
        snooze = db.query(Reminder).filter(Reminder.id == snooze_id).first()
        assert retry is not None and snooze is not None
        retry.next_retry_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        snooze.snoozed_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.add_all([retry, snooze])
        db.commit()
    finally:
        db.close()

    reminder_service.run_due_reminder_calls()

    db = SessionLocal()
    try:
        retry = db.query(Reminder).filter(Reminder.id == retry_id).first()
        snooze = db.query(Reminder).filter(Reminder.id == snooze_id).first()
        assert retry is not None and snooze is not None
        assert retry.status == "calling"
        assert snooze.status == "calling"
        assert set(calls) == {retry_id, snooze_id}
    finally:
        db.close()
        _delete_reminder(retry_id)
        _delete_reminder(snooze_id)


def test_call_again_snooze_mark_done_and_quota_unchanged(monkeypatch) -> None:
    reminder_id = _create_reminder("Recovery endpoint reminder", status="missed")
    try:
        before = client.get("/mail-calls/count-today", headers=_auth_headers())
        assert before.status_code == 200, before.text
        before_used = before.json()["used_calls_today"]

        calls: list[int] = []

        def fake_start(db, reminder, user):
            calls.append(reminder.id)
            reminder.provider_call_id = f"CA-{reminder.id}"
            reminder.status = "calling"
            reminder.called_at = datetime.now(timezone.utc)
            reminder.updated_at = datetime.now(timezone.utc)
            db.add(reminder)
            db.commit()

        monkeypatch.setattr(reminder_service, "start_reminder_call", fake_start)

        call_again = client.post(f"/reminders/{reminder_id}/call-again", headers=_auth_headers())
        assert call_again.status_code == 200, call_again.text
        assert calls == [reminder_id]

        snooze = client.post(f"/reminders/{reminder_id}/snooze", headers=_auth_headers(), json={"minutes": 10})
        assert snooze.status_code == 200, snooze.text
        assert snooze.json()["status"] == "snoozed"

        mark_done = client.post(f"/reminders/{reminder_id}/mark-done", headers=_auth_headers())
        assert mark_done.status_code == 200, mark_done.text
        assert mark_done.json()["status"] == "completed"

        after = client.get("/mail-calls/count-today", headers=_auth_headers())
        assert after.status_code == 200, after.text
        assert after.json()["used_calls_today"] == before_used
    finally:
        _delete_reminder(reminder_id)
