from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.database.session import SessionLocal
from app.models.recurring_reminder_rule import RecurringReminderRule
from app.models.reminder import Reminder
from app.models.user import User
from app.services.recurring_reminder_service import (
    cancel_recurring_rule,
    compute_next_occurrence,
    create_recurring_rule,
    generate_due_occurrences,
    pause_recurring_rule,
    resume_recurring_rule,
)


def _get_user() -> User:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        assert user is not None
        db.expunge(user)
        return user
    finally:
        db.close()


def _cleanup(title: str) -> None:
    db = SessionLocal()
    try:
        db.query(Reminder).filter(Reminder.title == title).delete(synchronize_session=False)
        db.query(RecurringReminderRule).filter(RecurringReminderRule.title == title).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_daily_weekly_monthly_and_interval_rules_generate_next_occurrence() -> None:
    user = _get_user()
    db = SessionLocal()
    title = f"Recurring Service Test {uuid4()}"
    try:
        daily = create_recurring_rule(
            db,
            user,
            SimpleNamespace(
                title=title,
                notes="Daily",
                timezone="Asia/Kolkata",
                repeat_type="daily",
                interval_value=None,
                interval_unit=None,
                days_of_week=None,
                day_of_month=None,
                time_of_day="20:00",
                source_type="manual",
                email_message_id=None,
                email_summary_id=None,
            ),
        )
        weekly = create_recurring_rule(
            db,
            user,
            SimpleNamespace(
                title=f"{title}-weekly",
                notes="Weekly",
                timezone="Asia/Kolkata",
                repeat_type="weekly",
                interval_value=None,
                interval_unit=None,
                days_of_week=["sunday"],
                day_of_month=None,
                time_of_day="19:00",
                source_type="manual",
                email_message_id=None,
                email_summary_id=None,
            ),
        )
        monthly = create_recurring_rule(
            db,
            user,
            SimpleNamespace(
                title=f"{title}-monthly",
                notes="Monthly",
                timezone="Asia/Kolkata",
                repeat_type="monthly",
                interval_value=None,
                interval_unit=None,
                days_of_week=None,
                day_of_month=5,
                time_of_day="09:00",
                source_type="manual",
                email_message_id=None,
                email_summary_id=None,
            ),
        )
        interval = create_recurring_rule(
            db,
            user,
            SimpleNamespace(
                title=f"{title}-interval",
                notes="Interval",
                timezone="Asia/Kolkata",
                repeat_type="custom_interval",
                interval_value=2,
                interval_unit="hours",
                days_of_week=None,
                day_of_month=None,
                time_of_day=None,
                source_type="manual",
                email_message_id=None,
                email_summary_id=None,
            ),
        )
        assert daily["next_occurrence_at"] is not None
        assert weekly["next_occurrence_at"] is not None
        assert monthly["next_occurrence_at"] is not None
        assert interval["next_occurrence_at"] is not None
    finally:
        _cleanup(title)
        _cleanup(f"{title}-weekly")
        _cleanup(f"{title}-monthly")
        _cleanup(f"{title}-interval")
        db.close()


def test_duplicate_prevention_and_pause_resume_cancel() -> None:
    user = _get_user()
    db = SessionLocal()
    title = f"Recurring Duplicate Test {uuid4()}"
    try:
        rule = create_recurring_rule(
            db,
            user,
            SimpleNamespace(
                title=title,
                notes="Duplicate guard",
                timezone="UTC",
                repeat_type="daily",
                interval_value=None,
                interval_unit=None,
                days_of_week=None,
                day_of_month=None,
                time_of_day="00:00",
                source_type="manual",
                email_message_id=None,
                email_summary_id=None,
            ),
        )
        rule_row = db.query(RecurringReminderRule).filter(RecurringReminderRule.id == rule["id"]).first()
        assert rule_row is not None
        rule_row.next_occurrence_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.add(rule_row)
        db.commit()

        created = generate_due_occurrences(db, now_utc=datetime.now(timezone.utc))
        assert len(created) == 1
        duplicate = generate_due_occurrences(db, now_utc=datetime.now(timezone.utc))
        assert len(duplicate) == 0

        paused = pause_recurring_rule(db, user, rule["id"])
        assert paused["status"] == "paused"
        resumed = resume_recurring_rule(db, user, rule["id"])
        assert resumed["status"] == "active"
        cancelled = cancel_recurring_rule(db, user, rule["id"])
        assert cancelled["status"] == "cancelled"
    finally:
        _cleanup(title)
        db.close()


def test_compute_next_occurrence_handles_weekdays() -> None:
    user = _get_user()
    db = SessionLocal()
    title = f"Recurring Weekdays Test {uuid4()}"
    try:
        rule = create_recurring_rule(
            db,
            user,
            SimpleNamespace(
                title=title,
                notes="Weekdays",
                timezone="Asia/Kolkata",
                repeat_type="weekdays",
                interval_value=None,
                interval_unit=None,
                days_of_week=None,
                day_of_month=None,
                time_of_day="09:00",
                source_type="manual",
                email_message_id=None,
                email_summary_id=None,
            ),
        )
        row = db.query(RecurringReminderRule).filter(RecurringReminderRule.id == rule["id"]).first()
        assert row is not None
        next_occurrence = compute_next_occurrence(row)
        assert next_occurrence is not None
    finally:
        _cleanup(title)
        db.close()
