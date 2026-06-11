from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.recurring_reminder_rule import RecurringReminderRule
from app.models.reminder import Reminder
from app.models.user import User
from app.core.timezone import normalize_timezone_name
from app.services.reminder_service import claim_reminder_for_call, reminder_to_item, start_reminder_call

logger = logging.getLogger(__name__)

REPEAT_TYPES = {"none", "daily", "weekly", "monthly", "weekdays", "custom_days", "custom_interval"}
WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _rule_status(rule: RecurringReminderRule) -> str:
    if rule.cancelled_at:
        return "cancelled"
    if rule.is_active is False:
        return "paused" if rule.paused_at else "paused"
    return "active"


def _normalize_days(value: list[str] | str | None) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                value = parsed
            else:
                value = [value]
        except Exception:
            value = [value]
    normalized = [item.strip().lower() for item in value if item and item.strip()]
    return normalized or None


def _serialize_days(value: list[str] | None) -> str | None:
    if not value:
        return None
    return json.dumps([item.strip().lower() for item in value if item and item.strip()])


def _validate_rule_payload(payload) -> None:
    repeat_type = payload.repeat_type
    if repeat_type not in REPEAT_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid repeat type")
    if repeat_type == "none":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Recurring reminder must repeat")
    if repeat_type in {"daily", "weekdays"} and not payload.time_of_day:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="time_of_day is required")
    if repeat_type in {"weekly", "custom_days"}:
        if not payload.days_of_week or not payload.time_of_day:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="days_of_week and time_of_day are required")
    if repeat_type == "monthly" and (payload.day_of_month is None or not payload.time_of_day):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="day_of_month and time_of_day are required")
    if repeat_type == "custom_interval":
        if payload.interval_value is None or not payload.interval_unit:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="interval_value and interval_unit are required")


def _rule_from_payload(user: User, payload) -> RecurringReminderRule:
    _validate_rule_payload(payload)
    timezone_name = normalize_timezone_name(payload.timezone or user.timezone or "UTC", "UTC")
    return RecurringReminderRule(
        user_id=user.id,
        title=payload.title.strip(),
        notes=(payload.notes or "").strip() or None,
        timezone=timezone_name,
        repeat_type=payload.repeat_type,
        interval_value=payload.interval_value,
        interval_unit=payload.interval_unit,
        days_of_week=_serialize_days(payload.days_of_week),
        day_of_month=payload.day_of_month,
        time_of_day=payload.time_of_day,
        is_active=True,
        source_type=payload.source_type or "manual",
        email_message_id=payload.email_message_id,
        email_summary_id=payload.email_summary_id,
        created_at=_now_utc(),
        updated_at=_now_utc(),
    )


def _parse_time_of_day(value: str | None) -> time | None:
    if not value:
        return None
    hours, minutes = value.split(":")
    return time(hour=int(hours), minute=int(minutes))


def _combine_local(day: date, clock: time, timezone_name: str) -> datetime:
    local_zone = ZoneInfo(normalize_timezone_name(timezone_name, "UTC"))
    return datetime.combine(day, clock, tzinfo=local_zone).astimezone(timezone.utc)


def _current_local(now_utc: datetime, timezone_name: str) -> datetime:
    return now_utc.astimezone(ZoneInfo(normalize_timezone_name(timezone_name, "UTC")))


def compute_next_occurrence(rule: RecurringReminderRule, reference: datetime | None = None) -> datetime | None:
    if not rule.is_active or rule.cancelled_at:
        return None
    now_utc = reference or _now_utc()
    local_zone = ZoneInfo(normalize_timezone_name(rule.timezone, "UTC"))
    local_now = now_utc.astimezone(local_zone)

    repeat_type = rule.repeat_type
    clock = _parse_time_of_day(rule.time_of_day) or time(hour=9, minute=0)

    if repeat_type == "daily":
        candidate_date = local_now.date()
        candidate = datetime.combine(candidate_date, clock, tzinfo=local_zone)
        if candidate <= local_now:
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc)

    if repeat_type == "weekdays":
        candidate = datetime.combine(local_now.date(), clock, tzinfo=local_zone)
        while candidate <= local_now or candidate.weekday() >= 5:
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc)

    if repeat_type in {"weekly", "custom_days"}:
        days = _normalize_days(rule.days_of_week) or []
        if not days:
            return None
        allowed = [WEEKDAY_INDEX[day] for day in days if day in WEEKDAY_INDEX]
        if not allowed:
            return None
        candidate_date = local_now.date()
        candidate = datetime.combine(candidate_date, clock, tzinfo=local_zone)
        for _ in range(14):
            if candidate > local_now and candidate.weekday() in allowed:
                return candidate.astimezone(timezone.utc)
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc)

    if repeat_type == "monthly":
        day_of_month = rule.day_of_month or 1
        year = local_now.year
        month = local_now.month
        for _ in range(24):
            try:
                candidate_local = datetime(year=year, month=month, day=day_of_month, hour=clock.hour, minute=clock.minute, tzinfo=local_zone)
            except ValueError:
                # clamp to last day of month
                next_month = month + 1
                next_year = year
                if next_month == 13:
                    next_month = 1
                    next_year += 1
                candidate_local = datetime(next_year, next_month, 1, clock.hour, clock.minute, tzinfo=local_zone) - timedelta(days=1)
            if candidate_local > local_now:
                return candidate_local.astimezone(timezone.utc)
            month += 1
            if month == 13:
                month = 1
                year += 1
        return None

    if repeat_type == "custom_interval":
        interval_value = max(int(rule.interval_value or 1), 1)
        unit = rule.interval_unit or "days"
        delta = {
            "minutes": timedelta(minutes=interval_value),
            "hours": timedelta(hours=interval_value),
            "days": timedelta(days=interval_value),
            "weeks": timedelta(weeks=interval_value),
            "months": timedelta(days=30 * interval_value),
        }.get(unit, timedelta(days=interval_value))
        base = rule.last_generated_at or now_utc
        candidate = base + delta
        if candidate <= now_utc:
            candidate = now_utc + delta
        return candidate

    return None


def create_recurring_rule(db: Session, user: User, payload) -> dict[str, object]:
    rule = _rule_from_payload(user, payload)
    if (rule.source_type or "").lower() in {"voice", "agent"}:
        existing = (
            db.query(RecurringReminderRule)
            .filter(
                RecurringReminderRule.user_id == user.id,
                RecurringReminderRule.cancelled_at.is_(None),
                RecurringReminderRule.title == rule.title,
                RecurringReminderRule.notes == rule.notes,
                RecurringReminderRule.timezone == rule.timezone,
                RecurringReminderRule.repeat_type == rule.repeat_type,
                RecurringReminderRule.interval_value == rule.interval_value,
                RecurringReminderRule.interval_unit == rule.interval_unit,
                RecurringReminderRule.days_of_week == rule.days_of_week,
                RecurringReminderRule.day_of_month == rule.day_of_month,
                RecurringReminderRule.time_of_day == rule.time_of_day,
                RecurringReminderRule.email_message_id == rule.email_message_id,
                RecurringReminderRule.email_summary_id == rule.email_summary_id,
            )
            .order_by(RecurringReminderRule.id.desc())
            .first()
        )
        if existing is not None:
            return recurring_rule_to_item(existing)
    rule.next_occurrence_at = compute_next_occurrence(rule)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return recurring_rule_to_item(rule)


def update_recurring_rule(db: Session, user: User, rule_id: int, payload) -> dict[str, object]:
    rule = get_recurring_rule_detail(db, user, rule_id)
    if payload.title is not None:
        rule.title = payload.title.strip()
    if payload.notes is not None:
        rule.notes = payload.notes.strip() or None
    if payload.timezone is not None:
        rule.timezone = payload.timezone.strip() or rule.timezone
    if payload.repeat_type is not None:
        rule.repeat_type = payload.repeat_type
    if payload.interval_value is not None:
        rule.interval_value = payload.interval_value
    if payload.interval_unit is not None:
        rule.interval_unit = payload.interval_unit
    if payload.days_of_week is not None:
        rule.days_of_week = _serialize_days(payload.days_of_week)
    if payload.day_of_month is not None:
        rule.day_of_month = payload.day_of_month
    if payload.time_of_day is not None:
        rule.time_of_day = payload.time_of_day
    if payload.is_active is not None:
        rule.is_active = payload.is_active
        if payload.is_active:
            rule.paused_at = None
            rule.cancelled_at = None
        else:
            rule.paused_at = _now_utc()
    if payload.source_type is not None:
        rule.source_type = payload.source_type
    if payload.email_message_id is not None:
        rule.email_message_id = payload.email_message_id
    if payload.email_summary_id is not None:
        rule.email_summary_id = payload.email_summary_id
    rule.next_occurrence_at = compute_next_occurrence(rule)
    rule.updated_at = _now_utc()
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return recurring_rule_to_item(rule)


def pause_recurring_rule(db: Session, user: User, rule_id: int) -> dict[str, object]:
    rule = get_recurring_rule_detail(db, user, rule_id)
    rule.is_active = False
    rule.paused_at = _now_utc()
    rule.updated_at = _now_utc()
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return recurring_rule_to_item(rule)


def resume_recurring_rule(db: Session, user: User, rule_id: int) -> dict[str, object]:
    rule = get_recurring_rule_detail(db, user, rule_id)
    rule.is_active = True
    rule.paused_at = None
    rule.cancelled_at = None
    rule.next_occurrence_at = compute_next_occurrence(rule)
    rule.updated_at = _now_utc()
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return recurring_rule_to_item(rule)


def cancel_recurring_rule(db: Session, user: User, rule_id: int) -> dict[str, object]:
    rule = get_recurring_rule_detail(db, user, rule_id)
    rule.is_active = False
    rule.cancelled_at = _now_utc()
    rule.next_occurrence_at = None
    rule.updated_at = _now_utc()
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return recurring_rule_to_item(rule)


def get_user_recurring_rules(db: Session, user: User) -> list[RecurringReminderRule]:
    return db.query(RecurringReminderRule).filter(RecurringReminderRule.user_id == user.id).order_by(RecurringReminderRule.created_at.desc()).all()


def get_recurring_rule_detail(db: Session, user: User, rule_id: int) -> RecurringReminderRule:
    rule = db.query(RecurringReminderRule).filter(RecurringReminderRule.user_id == user.id, RecurringReminderRule.id == rule_id).first()
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurring reminder not found")
    return rule


def recurring_rule_to_item(rule: RecurringReminderRule) -> dict[str, object]:
    return {
        "id": rule.id,
        "user_id": rule.user_id,
        "title": rule.title,
        "notes": rule.notes,
        "timezone": rule.timezone,
        "repeat_type": rule.repeat_type,
        "interval_value": rule.interval_value,
        "interval_unit": rule.interval_unit,
        "days_of_week": _normalize_days(rule.days_of_week),
        "day_of_month": rule.day_of_month,
        "time_of_day": rule.time_of_day,
        "is_active": rule.is_active,
        "paused_at": rule.paused_at,
        "cancelled_at": rule.cancelled_at,
        "last_generated_at": rule.last_generated_at,
        "next_occurrence_at": rule.next_occurrence_at,
        "source_type": rule.source_type,
        "email_message_id": rule.email_message_id,
        "email_summary_id": rule.email_summary_id,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
        "status": _rule_status(rule),
    }


def _rule_occurrence_exists(db: Session, rule_id: int, occurrence_at: datetime) -> bool:
    return db.query(Reminder.id).filter(Reminder.recurring_rule_id == rule_id, Reminder.reminder_at == occurrence_at).first() is not None


def _build_occurrence_reminder(rule: RecurringReminderRule, occurrence_at: datetime) -> Reminder:
    return Reminder(
        user_id=rule.user_id,
        recurring_rule_id=rule.id,
        title=rule.title,
        notes=rule.notes,
        reminder_at=occurrence_at,
        timezone=rule.timezone,
        phone_number=None,
        status="scheduled",
        retry_count=0,
        max_retry_attempts=3,
        created_at=_now_utc(),
        updated_at=_now_utc(),
    )


def generate_due_occurrences(db: Session, now_utc: datetime | None = None, limit: int = 25) -> list[Reminder]:
    now_utc = now_utc or _now_utc()
    due_rules = (
        db.query(RecurringReminderRule)
        .filter(
            RecurringReminderRule.is_active.is_(True),
            RecurringReminderRule.cancelled_at.is_(None),
            RecurringReminderRule.next_occurrence_at.is_not(None),
            RecurringReminderRule.next_occurrence_at <= now_utc,
        )
        .order_by(RecurringReminderRule.next_occurrence_at.asc())
        .limit(limit)
        .all()
    )
    created: list[Reminder] = []
    for rule in due_rules:
        occurrence_at = rule.next_occurrence_at
        if occurrence_at is None:
            continue
        if _rule_occurrence_exists(db, rule.id, occurrence_at):
            rule.last_generated_at = occurrence_at
            rule.next_occurrence_at = compute_next_occurrence(rule, reference=occurrence_at + timedelta(seconds=1))
            rule.updated_at = now_utc
            db.add(rule)
            continue
        reminder = _build_occurrence_reminder(rule, occurrence_at)
        created.append(reminder)
        db.add(reminder)
        rule.last_generated_at = occurrence_at
        rule.next_occurrence_at = compute_next_occurrence(rule, reference=occurrence_at + timedelta(seconds=1))
        rule.updated_at = now_utc
        db.add(rule)
    if created:
        db.commit()
        for reminder in created:
            db.refresh(reminder)
    elif due_rules:
        db.commit()
    return created


def get_rule_occurrences(db: Session, user: User, rule_id: int) -> list[Reminder]:
    return (
        db.query(Reminder)
        .join(RecurringReminderRule, Reminder.recurring_rule_id == RecurringReminderRule.id)
        .filter(Reminder.user_id == user.id, RecurringReminderRule.id == rule_id)
        .order_by(Reminder.reminder_at.desc())
        .all()
    )


def process_due_recurring_and_reminder_calls() -> None:
    from app.database.session import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        now_utc = _now_utc()
        generate_due_occurrences(db, now_utc=now_utc)
        due_reminders = db.query(Reminder).filter(
            or_(
                and_(Reminder.status == "scheduled", Reminder.reminder_at <= now_utc, Reminder.reminder_at >= now_utc - timedelta(seconds=120)),
                and_(Reminder.status == "retry_scheduled", Reminder.next_retry_at.is_not(None), Reminder.next_retry_at <= now_utc),
                and_(Reminder.status == "snoozed", Reminder.snoozed_until.is_not(None), Reminder.snoozed_until <= now_utc),
            )
        ).order_by(Reminder.reminder_at.asc(), Reminder.id.asc()).limit(25).all()
        for reminder in due_reminders:
            user = db.query(User).filter(User.id == reminder.user_id).first()
            if user is None:
                continue
            try:
                if not claim_reminder_for_call(db, reminder):
                    continue
                start_reminder_call(db, reminder, user)
            except Exception as exc:
                db.rollback()
                logger.error("Recurring reminder call failed reminder_id=%s user_id=%s error=%s", reminder.id, user.id, exc)
    finally:
        db.close()
