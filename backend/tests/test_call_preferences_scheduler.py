from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app.database.session import SessionLocal
from app.models.gmail_connection import GmailConnection
from app.models.user import User
from app.models.user_call_preference import UserCallPreference
from app.services import call_preferences_service as cps


def _cleanup_scheduler_users() -> None:
    db = SessionLocal()
    try:
        scheduler_users = db.query(User).filter(User.email.like("scheduler-%@example.com")).all()
        for user in scheduler_users:
            db.query(GmailConnection).filter(GmailConnection.user_id == user.id).delete(synchronize_session=False)
            db.query(UserCallPreference).filter(UserCallPreference.user_id == user.id).delete(synchronize_session=False)
            db.query(User).filter(User.id == user.id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _create_user_with_preferences(slot_time: str, minimum: int = 1) -> int:
    db = SessionLocal()
    try:
        email = f"scheduler-{datetime.now(timezone.utc).timestamp()}@example.com"
        user = User(
            email=email,
            name="Scheduler User",
            phone_number="+919843731545",
            timezone="Asia/Kolkata",
            preferred_language="English",
            hashed_password="hash",
            is_active=True,
            is_verified=True,
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
                timezone="Asia/Kolkata",
                call_slot_1_time=slot_time,
                call_slot_1_enabled=True,
                call_slot_2_time="13:00",
                call_slot_2_enabled=False,
                call_slot_3_time="19:00",
                call_slot_3_enabled=False,
                minimum_new_emails_to_call=minimum,
                skip_if_no_new_emails=True,
                avoid_repeating_delivered_emails=True,
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        return user.id
    finally:
        db.close()


def test_scheduler_starts_call_when_slot_is_due_and_minimum_met(monkeypatch) -> None:
    _cleanup_scheduler_users()
    slot_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M")
    user_id = _create_user_with_preferences(slot_time, minimum=1)
    calls: list[tuple[int, int]] = []

    monkeypatch.setattr(cps, "get_mail_call_count_today", lambda db, user: {"used_calls_today": 0})
    monkeypatch.setattr(cps, "list_pending_today_summaries", lambda db, user: [object(), object()])
    monkeypatch.setattr(cps, "list_todays_summaries", lambda db, user: [object(), object()])
    monkeypatch.setattr(cps, "_mail_summary_call_exists_for_slot", lambda db, user_id, call_date, slot_time: False)
    monkeypatch.setattr(cps, "prepare_mail_summary_call", lambda db, user, include_delivered=False: {"call_log_id": 999, "summary_count": 2})
    monkeypatch.setattr(cps, "start_mail_summary_voice_call", lambda db, user, call_log_id: calls.append((user.id, call_log_id)))

    cps.run_due_mail_summary_calls()
    assert calls == [(user_id, 999)]


def test_scheduler_skips_when_no_new_emails(monkeypatch) -> None:
    _cleanup_scheduler_users()
    slot_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M")
    _create_user_with_preferences(slot_time, minimum=1)
    calls: list[int] = []

    monkeypatch.setattr(cps, "get_mail_call_count_today", lambda db, user: {"used_calls_today": 0})
    monkeypatch.setattr(cps, "list_pending_today_summaries", lambda db, user: [])
    monkeypatch.setattr(cps, "list_todays_summaries", lambda db, user: [])
    monkeypatch.setattr(cps, "_mail_summary_call_exists_for_slot", lambda db, user_id, call_date, slot_time: False)
    monkeypatch.setattr(cps, "prepare_mail_summary_call", lambda db, user, include_delivered=False: {"call_log_id": 999, "summary_count": 1})
    monkeypatch.setattr(cps, "start_mail_summary_voice_call", lambda db, user, call_log_id: calls.append(call_log_id))

    cps.run_due_mail_summary_calls()
    assert calls == []


def test_scheduler_skips_when_below_minimum(monkeypatch) -> None:
    _cleanup_scheduler_users()
    slot_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M")
    _create_user_with_preferences(slot_time, minimum=3)
    calls: list[int] = []

    monkeypatch.setattr(cps, "get_mail_call_count_today", lambda db, user: {"used_calls_today": 0})
    monkeypatch.setattr(cps, "list_pending_today_summaries", lambda db, user: [object()])
    monkeypatch.setattr(cps, "list_todays_summaries", lambda db, user: [object()])
    monkeypatch.setattr(cps, "_mail_summary_call_exists_for_slot", lambda db, user_id, call_date, slot_time: False)
    monkeypatch.setattr(cps, "prepare_mail_summary_call", lambda db, user, include_delivered=False: calls.append(user.id))
    monkeypatch.setattr(cps, "start_mail_summary_voice_call", lambda db, user, call_log_id: calls.append(call_log_id))

    cps.run_due_mail_summary_calls()
    assert calls == []
