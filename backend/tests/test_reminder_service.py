from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from app.database.session import SessionLocal
from app.models.reminder import Reminder
from app.models.user import User
from app.schemas.reminder import ReminderCreate, ReminderUpdate
from app.services.reminder_service import cancel_reminder, create_reminder, get_reminder, list_reminders, mark_reminder_done, update_reminder


def _get_user(email: str = "browsertest@example.com") -> User:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None
        db.expunge(user)
        return user
    finally:
        db.close()


def _make_future_payload(minutes: int = 15, timezone_name: str = "Asia/Kolkata", phone_number: str | None = None) -> ReminderCreate:
    local_now = datetime.now(ZoneInfo(timezone_name)) + timedelta(minutes=minutes)
    return ReminderCreate(
        title="Submit ML assignment",
        notes="Upload final notebook before deadline",
        reminder_date=local_now.date().isoformat(),
        reminder_time=local_now.strftime("%H:%M"),
        timezone=timezone_name,
        phone_number=phone_number,
    )


def test_create_reminder_with_future_time_and_profile_phone() -> None:
    user = _get_user()
    db = SessionLocal()
    try:
        payload = _make_future_payload(phone_number=None)
        reminder = create_reminder(db, user, payload)
        assert reminder["status"] == "scheduled"
        assert reminder["phone_number"] == user.phone_number
        assert reminder["reminder_at"].tzinfo is not None
    finally:
        db.query(Reminder).filter(Reminder.title == "Submit ML assignment").delete(synchronize_session=False)
        db.commit()
        db.close()


def test_reject_past_reminder() -> None:
    user = _get_user()
    db = SessionLocal()
    try:
        past = datetime.now(ZoneInfo("Asia/Kolkata")) - timedelta(minutes=5)
        payload = ReminderCreate(
            title="Past reminder",
            notes=None,
            reminder_date=past.date().isoformat(),
            reminder_time=past.strftime("%H:%M"),
            timezone="Asia/Kolkata",
            phone_number="+919843731545",
        )
        with pytest.raises(HTTPException):
            create_reminder(db, user, payload)
    finally:
        db.query(Reminder).filter(Reminder.title == "Past reminder").delete(synchronize_session=False)
        db.commit()
        db.close()


def test_timezone_conversion_to_utc() -> None:
    user = _get_user()
    db = SessionLocal()
    try:
        payload = _make_future_payload(minutes=20, timezone_name="Asia/Kolkata", phone_number="+919843731545")
        reminder = create_reminder(db, user, payload)
        stored = db.query(Reminder).filter(Reminder.id == reminder["id"]).first()
        assert stored is not None
        expected_local = datetime.strptime(f"{payload.reminder_date} {payload.reminder_time}", "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo("Asia/Kolkata"))
        expected_utc = expected_local.astimezone(timezone.utc)
        assert stored.reminder_at.replace(tzinfo=timezone.utc) == expected_utc
    finally:
        db.query(Reminder).filter(Reminder.title == "Submit ML assignment").delete(synchronize_session=False)
        db.commit()
        db.close()


def test_reject_when_no_phone_available() -> None:
    db = SessionLocal()
    try:
        unique_email = f"reminder-no-phone-{uuid4()}@example.com"
        user = User(
            email=unique_email,
            name="No Phone",
            phone_number=None,
            timezone="Asia/Kolkata",
            preferred_language="English",
            hashed_password="hash",
            is_active=True,
            is_verified=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        payload = _make_future_payload(phone_number=None)
        with pytest.raises(HTTPException):
            create_reminder(db, user, payload)
    finally:
        db.query(Reminder).filter(Reminder.title == "Submit ML assignment").delete(synchronize_session=False)
        db.query(User).filter(User.email.like("reminder-no-phone-%@example.com")).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_list_get_update_cancel_and_cross_user_access() -> None:
    user = _get_user()
    db = SessionLocal()
    try:
        payload = _make_future_payload(minutes=25)
        reminder = create_reminder(db, user, payload)
        reminder_id = reminder["id"]

        listed = list_reminders(db, user, include_cancelled=False)
        assert any(item.id == reminder_id for item in listed)

        fetched = get_reminder(db, user, reminder_id)
        assert fetched.id == reminder_id

        updated = update_reminder(
            db,
            user,
            reminder_id,
            ReminderUpdate(
                title="Updated title",
                notes="Updated notes",
                reminder_date=payload.reminder_date,
                reminder_time=payload.reminder_time,
                timezone="Asia/Kolkata",
                phone_number="+919843731545",
            ),
        )
        assert updated["title"] == "Updated title"

        cancelled = cancel_reminder(db, user, reminder_id)
        assert cancelled["status"] == "cancelled"

        upcoming = list_reminders(db, user, include_cancelled=False)
        assert all(item.id != reminder_id for item in upcoming)

        with pytest.raises(HTTPException):
            update_reminder(
                db,
                user,
                reminder_id,
                ReminderUpdate(title="Should fail"),
            )

        other_user = User(
            email=f"reminder-other-{uuid4()}@example.com",
            name="Other User",
            phone_number="+919999999998",
            timezone="Asia/Kolkata",
            preferred_language="English",
            hashed_password="hash",
            is_active=True,
            is_verified=False,
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)

        with pytest.raises(HTTPException):
            get_reminder(db, other_user, reminder_id)
    finally:
        db.query(Reminder).filter(Reminder.title.in_(["Submit ML assignment", "Updated title"])).delete(synchronize_session=False)
        db.query(User).filter(User.email.like("reminder-other-%@example.com")).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_completed_reminder_cannot_be_cancelled() -> None:
    user = _get_user()
    db = SessionLocal()
    try:
        payload = _make_future_payload(minutes=25)
        reminder = create_reminder(db, user, payload)
        reminder_id = reminder["id"]
        mark_reminder_done(db, user, reminder_id)
        with pytest.raises(HTTPException):
            cancel_reminder(db, user, reminder_id)
    finally:
        db.query(Reminder).filter(Reminder.title == "Submit ML assignment").delete(synchronize_session=False)
        db.commit()
        db.close()
