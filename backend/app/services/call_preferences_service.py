from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
import logging
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.email_summary import EmailSummary
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.user import User
from app.models.user_call_preference import UserCallPreference
from app.services.mail_summary_call_service import (
    get_mail_call_count_today,
    list_pending_today_summaries,
    list_todays_summaries,
    prepare_mail_summary_call,
)
from app.services.voice_call_service import start_mail_summary_voice_call

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "Asia/Kolkata"
DEFAULT_SLOT_TIMES = ("09:00", "13:00", "19:00")
VALID_MINIMUM_EMAIL_COUNTS = {1, 3, 5}


@dataclass(slots=True)
class ScheduledSummaryPreview:
    next_scheduled_summary_call_at: datetime | None
    next_scheduled_summary_call_status: str | None
    pending_new_email_summaries: int
    would_call_next_slot: bool
    next_slot_label: str | None
    next_slot_time: str | None


def _normalize_time_string(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    candidate = value.strip()
    try:
        parsed = datetime.strptime(candidate, "%H:%M").time()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Times must be HH:MM") from exc
    return parsed.strftime("%H:%M")


def _validate_timezone_name(name: str | None) -> str:
    timezone_name = (name or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
    try:
        ZoneInfo(timezone_name)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid timezone") from exc
    return timezone_name


def _default_preferences(user: User) -> UserCallPreference:
    return UserCallPreference(
        user_id=user.id,
        timezone=_validate_timezone_name(user.timezone or DEFAULT_TIMEZONE),
        call_slot_1_time=DEFAULT_SLOT_TIMES[0],
        call_slot_1_enabled=True,
        call_slot_2_time=DEFAULT_SLOT_TIMES[1],
        call_slot_2_enabled=True,
        call_slot_3_time=DEFAULT_SLOT_TIMES[2],
        call_slot_3_enabled=True,
        minimum_new_emails_to_call=1,
        skip_if_no_new_emails=True,
        avoid_repeating_delivered_emails=True,
        updated_at=datetime.now(timezone.utc),
    )


def get_or_create_call_preferences(db: Session, user: User) -> UserCallPreference:
    prefs = db.query(UserCallPreference).filter(UserCallPreference.user_id == user.id).first()
    if prefs is not None:
        return prefs
    prefs = _default_preferences(user)
    db.add(prefs)
    db.commit()
    db.refresh(prefs)
    return prefs


def _candidate_summaries(db: Session, user: User, include_delivered: bool) -> list[EmailSummary]:
    return list_todays_summaries(db, user) if include_delivered else list_pending_today_summaries(db, user)


def _slot_definitions(prefs: UserCallPreference) -> list[tuple[str, str, bool]]:
    return [
        ("Call 1", prefs.call_slot_1_time, prefs.call_slot_1_enabled),
        ("Call 2", prefs.call_slot_2_time, prefs.call_slot_2_enabled),
        ("Call 3", prefs.call_slot_3_time, prefs.call_slot_3_enabled),
    ]


def _build_preview(db: Session, user: User, prefs: UserCallPreference) -> ScheduledSummaryPreview:
    local_zone = ZoneInfo(prefs.timezone or user.timezone or DEFAULT_TIMEZONE)
    local_now = datetime.now(local_zone)
    pending_count = len(list_pending_today_summaries(db, user))

    next_slot_label = None
    next_slot_time = None
    next_call_at = None
    would_call = False
    status_text = "No enabled call slots"

    for label, slot_time, enabled in _slot_definitions(prefs):
        if not enabled:
            continue
        slot_clock = datetime.strptime(slot_time, "%H:%M").time()
        slot_dt = datetime.combine(local_now.date(), slot_clock, tzinfo=local_zone)
        if slot_dt < local_now:
            slot_dt = slot_dt + timedelta(days=1)
        if next_call_at is None or slot_dt < next_call_at.astimezone(local_zone):
            next_slot_label = label
            next_slot_time = slot_time
            next_call_at = slot_dt.astimezone(timezone.utc)

    if next_call_at is not None:
        if pending_count == 0 and prefs.skip_if_no_new_emails:
            status_text = "Will skip because there are no new emails"
        elif pending_count < prefs.minimum_new_emails_to_call:
            status_text = f"Will skip because minimum is {prefs.minimum_new_emails_to_call}"
        else:
            status_text = f"Will call because minimum is {prefs.minimum_new_emails_to_call}"
            would_call = True

    return ScheduledSummaryPreview(
        next_scheduled_summary_call_at=next_call_at,
        next_scheduled_summary_call_status=status_text,
        pending_new_email_summaries=pending_count,
        would_call_next_slot=would_call,
        next_slot_label=next_slot_label,
        next_slot_time=next_slot_time,
    )


def call_preferences_to_item(db: Session, user: User, prefs: UserCallPreference) -> dict[str, object]:
    preview = _build_preview(db, user, prefs)
    return {
        "timezone": prefs.timezone,
        "call_slot_1_time": prefs.call_slot_1_time,
        "call_slot_1_enabled": prefs.call_slot_1_enabled,
        "call_slot_2_time": prefs.call_slot_2_time,
        "call_slot_2_enabled": prefs.call_slot_2_enabled,
        "call_slot_3_time": prefs.call_slot_3_time,
        "call_slot_3_enabled": prefs.call_slot_3_enabled,
        "minimum_new_emails_to_call": prefs.minimum_new_emails_to_call,
        "skip_if_no_new_emails": prefs.skip_if_no_new_emails,
        "avoid_repeating_delivered_emails": prefs.avoid_repeating_delivered_emails,
        "next_scheduled_summary_call_at": preview.next_scheduled_summary_call_at,
        "next_scheduled_summary_call_status": preview.next_scheduled_summary_call_status,
        "pending_new_email_summaries": preview.pending_new_email_summaries,
        "would_call_next_slot": preview.would_call_next_slot,
        "next_slot_label": preview.next_slot_label,
        "next_slot_time": preview.next_slot_time,
    }


def update_call_preferences(db: Session, user: User, payload) -> UserCallPreference:
    prefs = get_or_create_call_preferences(db, user)
    if payload.timezone is not None:
        prefs.timezone = _validate_timezone_name(payload.timezone)
    for field, fallback in (
        ("call_slot_1_time", prefs.call_slot_1_time or DEFAULT_SLOT_TIMES[0]),
        ("call_slot_2_time", prefs.call_slot_2_time or DEFAULT_SLOT_TIMES[1]),
        ("call_slot_3_time", prefs.call_slot_3_time or DEFAULT_SLOT_TIMES[2]),
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(prefs, field, _normalize_time_string(value, fallback))
    for field in ("call_slot_1_enabled", "call_slot_2_enabled", "call_slot_3_enabled", "skip_if_no_new_emails", "avoid_repeating_delivered_emails"):
        value = getattr(payload, field)
        if value is not None:
            setattr(prefs, field, bool(value))
    if payload.minimum_new_emails_to_call is not None:
        minimum = int(payload.minimum_new_emails_to_call)
        if minimum not in VALID_MINIMUM_EMAIL_COUNTS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="minimum_new_emails_to_call must be 1, 3, or 5")
        prefs.minimum_new_emails_to_call = minimum
    prefs.updated_at = datetime.now(timezone.utc)
    db.add(prefs)
    db.commit()
    db.refresh(prefs)
    return prefs


def _slot_matches(local_now: datetime, slot_time: str) -> bool:
    slot_clock = datetime.strptime(slot_time, "%H:%M").time()
    return local_now.hour == slot_clock.hour and local_now.minute == slot_clock.minute


def _mail_summary_call_exists_for_slot(db: Session, user_id: int, call_date, slot_time: str) -> bool:
    return (
        db.query(MailSummaryCallLog.id)
        .filter(
            MailSummaryCallLog.user_id == user_id,
            MailSummaryCallLog.call_type == "mail_summary",
            MailSummaryCallLog.call_date == call_date,
            MailSummaryCallLog.call_time == datetime.strptime(slot_time, "%H:%M").time(),
        )
        .first()
        is not None
    )


def run_due_mail_summary_calls() -> None:
    from app.database.session import SessionLocal
    from app.models.gmail_connection import GmailConnection

    db = SessionLocal()
    try:
        users = (
            db.query(User)
            .join(UserCallPreference, UserCallPreference.user_id == User.id)
            .join(GmailConnection, GmailConnection.user_id == User.id)
            .filter(GmailConnection.is_connected.is_(True))
            .order_by(User.id.asc())
            .all()
        )
        for user in users:
            prefs = get_or_create_call_preferences(db, user)
            local_zone = ZoneInfo(prefs.timezone or user.timezone or DEFAULT_TIMEZONE)
            local_now = datetime.now(local_zone)
            counts = get_mail_call_count_today(db, user)
            if counts["used_calls_today"] >= 3:
                logger.info("Scheduled mail summary skipped user_id=%s reason=daily_limit_reached", user.id)
                continue
            for label, slot_time, enabled in _slot_definitions(prefs):
                if not enabled or not _slot_matches(local_now, slot_time):
                    continue
                if _mail_summary_call_exists_for_slot(db, user.id, local_now.date(), slot_time):
                    continue
                candidate_summaries = _candidate_summaries(db, user, include_delivered=not prefs.avoid_repeating_delivered_emails)
                if not candidate_summaries and prefs.skip_if_no_new_emails:
                    logger.info("Scheduled mail summary skipped user_id=%s slot=%s reason=no_new_emails", user.id, label)
                    continue
                if len(candidate_summaries) < prefs.minimum_new_emails_to_call:
                    logger.info(
                        "Scheduled mail summary skipped user_id=%s slot=%s reason=below_minimum pending=%s minimum=%s",
                        user.id,
                        label,
                        len(candidate_summaries),
                        prefs.minimum_new_emails_to_call,
                    )
                    continue
                try:
                    prepared = prepare_mail_summary_call(db, user, include_delivered=not prefs.avoid_repeating_delivered_emails)
                    start_mail_summary_voice_call(db, user, prepared["call_log_id"])
                    logger.info(
                        "Scheduled mail summary started user_id=%s slot=%s call_log_id=%s pending=%s",
                        user.id,
                        label,
                        prepared["call_log_id"],
                        len(candidate_summaries),
                    )
                except Exception as exc:
                    logger.error("Scheduled mail summary failed user_id=%s slot=%s error=%s", user.id, label, str(exc))
                break
    finally:
        db.close()
