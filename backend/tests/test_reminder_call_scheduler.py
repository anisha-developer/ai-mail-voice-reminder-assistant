from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.database.session import SessionLocal
from app.config import settings
from app.models.reminder import Reminder
from app.models.user import User
from app.services import reminder_service


def _get_user() -> User:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        assert user is not None
        db.expunge(user)
        return user
    finally:
        db.close()


def _create_reminder(offset_minutes: int, title: str, status: str = "scheduled") -> int:
    user = _get_user()
    db = SessionLocal()
    try:
        reminder_at = datetime.now(ZoneInfo("Asia/Kolkata")) + timedelta(minutes=offset_minutes)
        reminder = Reminder(
            user_id=user.id,
            title=title,
            notes="Call me back",
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


def _cleanup(title: str) -> None:
    db = SessionLocal()
    try:
        db.query(Reminder).filter(Reminder.title == title).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_due_scheduled_reminder_is_claimed_and_called(monkeypatch) -> None:
    title = "Scheduler due test"
    reminder_id = _create_reminder(-1, title)
    calls: list[int] = []

    def fake_start(db, reminder, user):
        calls.append(reminder.id)
        reminder.provider_call_id = f"CA-{reminder.id}"
        reminder.status = "calling"
        reminder.called_at = datetime.now(timezone.utc)
        reminder.updated_at = datetime.now(timezone.utc)
        db.add(reminder)
        db.commit()
        return {"provider_call_id": reminder.provider_call_id}

    monkeypatch.setattr(reminder_service, "start_reminder_call", fake_start)
    monkeypatch.setattr(settings, "reminder_calls_enabled", True)
    monkeypatch.setattr(settings, "reminder_due_grace_seconds", 120)
    reminder_service.run_due_reminder_calls()

    db = SessionLocal()
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        assert reminder is not None
        assert calls == [reminder_id]
        assert reminder.status == "calling"
        assert reminder.provider_call_id == f"CA-{reminder_id}"
    finally:
        db.close()
        _cleanup(title)


def test_cancelled_and_completed_reminders_are_skipped(monkeypatch) -> None:
    cancelled_id = _create_reminder(-1, "Scheduler cancelled test", status="cancelled")
    completed_id = _create_reminder(-1, "Scheduler completed test", status="completed")
    calls: list[int] = []
    monkeypatch.setattr(reminder_service, "start_reminder_call", lambda db, reminder, user: calls.append(reminder.id))
    monkeypatch.setattr(settings, "reminder_calls_enabled", True)
    reminder_service.run_due_reminder_calls()
    assert calls == []

    db = SessionLocal()
    try:
        cancelled = db.query(Reminder).filter(Reminder.id == cancelled_id).first()
        completed = db.query(Reminder).filter(Reminder.id == completed_id).first()
        assert cancelled is not None and completed is not None
        assert cancelled.status == "cancelled"
        assert completed.status == "completed"
    finally:
        db.close()
        _cleanup("Scheduler cancelled test")
        _cleanup("Scheduler completed test")


def test_old_reminder_beyond_grace_is_left_for_retry_flow(monkeypatch) -> None:
    title = "Scheduler stale test"
    reminder_id = _create_reminder(-30, title)
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
    monkeypatch.setattr(settings, "reminder_due_grace_seconds", 120)
    reminder_service.run_due_reminder_calls()

    db = SessionLocal()
    try:
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        assert reminder is not None
        assert calls == [reminder_id]
        assert reminder.status == "calling"
    finally:
        db.close()
        _cleanup(title)


def test_duplicate_scheduler_run_does_not_recreate_call(monkeypatch) -> None:
    title = "Scheduler duplicate test"
    reminder_id = _create_reminder(-1, title)
    calls: list[int] = []

    def fake_start(db, reminder, user):
        calls.append(reminder.id)
        reminder.provider_call_id = f"CA-{reminder.id}"
        reminder.status = "calling"
        reminder.called_at = datetime.now(timezone.utc)
        db.add(reminder)
        db.commit()
        return {"provider_call_id": reminder.provider_call_id}

    monkeypatch.setattr(reminder_service, "start_reminder_call", fake_start)
    monkeypatch.setattr(settings, "reminder_calls_enabled", True)
    reminder_service.run_due_reminder_calls()
    reminder_service.run_due_reminder_calls()
    assert calls == [reminder_id]

    _cleanup(title)
