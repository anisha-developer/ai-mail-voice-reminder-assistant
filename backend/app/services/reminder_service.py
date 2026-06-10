from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.reminder import Reminder
from app.models.user import User
from app.services.reminder_voice_service import REMINDER_PROVIDER_TWILIO, start_reminder_call

logger = logging.getLogger(__name__)

REMINDER_STATUSES = {"scheduled", "calling", "completed", "failed", "cancelled", "retry_scheduled", "missed", "snoozed"}
RETRY_DELAYS_MINUTES = {1: 2, 2: 5, 3: 10}


def _user_timezone_name(user: User, timezone_name: str | None) -> str:
    return (timezone_name or user.timezone or "UTC").strip() or "UTC"


def _parse_local_reminder_datetime(reminder_date: str, reminder_time: str, timezone_name: str) -> datetime:
    try:
        local_zone = ZoneInfo(timezone_name)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid timezone") from exc
    try:
        parsed_date = datetime.strptime(reminder_date, "%Y-%m-%d").date()
        parsed_time = datetime.strptime(reminder_time, "%H:%M").time()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid reminder date or time") from exc
    local_dt = datetime.combine(parsed_date, parsed_time, tzinfo=local_zone)
    return local_dt.astimezone(timezone.utc)


def _resolve_phone(user: User, phone_number: str | None) -> str:
    phone = (phone_number or user.phone_number or "").strip()
    if not phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone number is required")
    if not phone.startswith("+") or len(phone) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone number")
    return phone


def create_reminder(db: Session, user: User, payload) -> dict[str, object]:
    reminder_time = getattr(payload, "time_of_day", None) or getattr(payload, "reminder_time", None)
    reminder_at = _parse_local_reminder_datetime(payload.reminder_date, reminder_time, _user_timezone_name(user, payload.timezone))
    if reminder_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reminder time must be in the future")
    reminder = Reminder(
        user_id=user.id,
        title=payload.title.strip(),
        notes=(payload.notes or "").strip() or None,
        reminder_at=reminder_at,
        timezone=_user_timezone_name(user, payload.timezone),
        phone_number=_resolve_phone(user, payload.phone_number),
        status="scheduled",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder_to_item(reminder)


def list_reminders(db: Session, user: User, include_cancelled: bool = False) -> list[Reminder]:
    query = db.query(Reminder).filter(Reminder.user_id == user.id)
    if not include_cancelled:
        query = query.filter(Reminder.status != "cancelled")
    return query.order_by(Reminder.reminder_at.asc(), Reminder.id.desc()).all()


def _next_retry_delay_minutes(retry_count: int) -> int:
    return RETRY_DELAYS_MINUTES.get(retry_count, 10)


def _clear_future_call_state(reminder: Reminder) -> None:
    reminder.provider = reminder.provider or REMINDER_PROVIDER_TWILIO
    reminder.provider_call_id = None
    reminder.called_at = None


def get_reminder(db: Session, user: User, reminder_id: int) -> Reminder:
    reminder = db.query(Reminder).filter(Reminder.user_id == user.id, Reminder.id == reminder_id).first()
    if reminder is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reminder not found")
    return reminder


def update_reminder(db: Session, user: User, reminder_id: int, payload) -> dict[str, object]:
    reminder = get_reminder(db, user, reminder_id)
    if reminder.status in {"cancelled", "completed"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reminder can no longer be updated")
    if payload.title is not None:
        reminder.title = payload.title.strip()
    if payload.notes is not None:
        reminder.notes = payload.notes.strip() or None
    if payload.timezone is not None or payload.reminder_date is not None or payload.reminder_time is not None:
        reminder_date = payload.reminder_date or reminder.reminder_at.astimezone(ZoneInfo(reminder.timezone or user.timezone or "UTC")).date().isoformat()
        reminder_time = (
            getattr(payload, "time_of_day", None)
            or getattr(payload, "reminder_time", None)
            or reminder.reminder_at.astimezone(ZoneInfo(reminder.timezone or user.timezone or "UTC")).time().strftime("%H:%M")
        )
        reminder.timezone = _user_timezone_name(user, payload.timezone or reminder.timezone)
        reminder.reminder_at = _parse_local_reminder_datetime(reminder_date, reminder_time, reminder.timezone)
    if payload.phone_number is not None:
        reminder.phone_number = _resolve_phone(user, payload.phone_number)
    if payload.status is not None and payload.status in REMINDER_STATUSES:
        reminder.status = payload.status
    reminder.updated_at = datetime.now(timezone.utc)
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder_to_item(reminder)


def cancel_reminder(db: Session, user: User, reminder_id: int) -> dict[str, object]:
    reminder = get_reminder(db, user, reminder_id)
    reminder.status = "cancelled"
    reminder.next_retry_at = None
    reminder.snoozed_until = None
    reminder.updated_at = datetime.now(timezone.utc)
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder_to_item(reminder)


def get_due_reminders(db: Session, now_utc: datetime, grace_seconds: int, limit: int = 10) -> list[Reminder]:
    return (
        db.query(Reminder)
        .filter(
            (
                (Reminder.status == "scheduled")
                & (Reminder.reminder_at <= now_utc)
                & (Reminder.reminder_at >= now_utc - timedelta(seconds=grace_seconds))
            )
            | ((Reminder.status == "retry_scheduled") & (Reminder.next_retry_at.is_not(None)) & (Reminder.next_retry_at <= now_utc))
            | ((Reminder.status == "snoozed") & (Reminder.snoozed_until.is_not(None)) & (Reminder.snoozed_until <= now_utc))
        )
        .order_by(Reminder.reminder_at.asc(), Reminder.id.asc())
        .limit(limit)
        .all()
    )


def mark_reminder_calling(db: Session, reminder: Reminder, provider_call_id: str | None = None) -> None:
    reminder.status = "calling"
    reminder.provider = "twilio"
    reminder.provider_call_id = provider_call_id or reminder.provider_call_id
    reminder.last_call_status = "calling"
    reminder.updated_at = datetime.now(timezone.utc)
    db.add(reminder)
    db.commit()


def mark_reminder_completed(db: Session, reminder: Reminder, provider_call_id: str | None = None) -> None:
    reminder.status = "completed"
    reminder.provider_call_id = provider_call_id or reminder.provider_call_id
    reminder.called_at = datetime.now(timezone.utc)
    reminder.last_error = None
    reminder.last_call_status = "completed"
    reminder.next_retry_at = None
    reminder.snoozed_until = None
    reminder.updated_at = datetime.now(timezone.utc)
    db.add(reminder)
    db.commit()


def mark_reminder_failed(db: Session, reminder: Reminder, error_message: str) -> None:
    reminder.status = "failed"
    reminder.last_call_status = reminder.last_call_status or "failed"
    reminder.last_error = error_message[:500]
    reminder.updated_at = datetime.now(timezone.utc)
    db.add(reminder)
    db.commit()


def schedule_retry_after_failed_call(db: Session, reminder: Reminder, call_status: str) -> Reminder:
    normalized = (call_status or "").replace("-", "_").lower()
    reminder.last_call_status = normalized
    reminder.retry_count = (reminder.retry_count or 0) + 1
    if reminder.retry_count < reminder.max_retry_attempts:
        delay_minutes = _next_retry_delay_minutes(reminder.retry_count)
        reminder.status = "retry_scheduled"
        reminder.next_retry_at = datetime.now(timezone.utc) + timedelta(minutes=delay_minutes)
        reminder.last_error = normalized
    else:
        reminder.status = "missed"
        reminder.next_retry_at = None
        reminder.last_error = "missed after max retry attempts"
    reminder.updated_at = datetime.now(timezone.utc)
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


def get_retry_due_reminders(db: Session, now_utc: datetime, limit: int = 10) -> list[Reminder]:
    return (
        db.query(Reminder)
        .filter(
            ((Reminder.status == "scheduled") & (Reminder.reminder_at <= now_utc))
            | ((Reminder.status == "retry_scheduled") & (Reminder.next_retry_at.is_not(None)) & (Reminder.next_retry_at <= now_utc))
            | ((Reminder.status == "snoozed") & (Reminder.snoozed_until.is_not(None)) & (Reminder.snoozed_until <= now_utc))
        )
        .order_by(Reminder.updated_at.asc(), Reminder.id.asc())
        .limit(limit)
        .all()
    )


def claim_reminder_for_call(db: Session, reminder: Reminder) -> bool:
    current = db.query(Reminder).filter(Reminder.id == reminder.id).first()
    if current is None or current.status not in {"scheduled", "retry_scheduled", "snoozed"}:
        return False
    current.status = "calling"
    current.provider = REMINDER_PROVIDER_TWILIO
    current.last_call_status = "calling"
    current.updated_at = datetime.now(timezone.utc)
    db.add(current)
    db.commit()
    db.refresh(current)
    reminder.status = current.status
    reminder.provider = current.provider
    reminder.last_call_status = current.last_call_status
    reminder.updated_at = current.updated_at
    return True


def process_twilio_reminder_status_callback(
    db: Session,
    reminder_id: int,
    call_sid: str | None,
    call_status: str,
    call_duration: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if reminder is None:
        return
    reminder.provider = "twilio"
    if call_sid:
        reminder.provider_call_id = call_sid
    normalized = (call_status or "").replace("-", "_").lower()
    if normalized == "completed":
        reminder.status = "completed"
        reminder.called_at = reminder.called_at or datetime.now(timezone.utc)
        reminder.last_error = None
        reminder.last_call_status = "completed"
        reminder.next_retry_at = None
        reminder.snoozed_until = None
    elif normalized in {"failed", "busy", "no_answer", "canceled"}:
        schedule_retry_after_failed_call(db, reminder, normalized)
        if reminder.status == "missed":
            reminder.last_error = "missed after max retry attempts"
        else:
            reminder.last_error = normalized
    elif normalized in {"initiated", "ringing", "in_progress", "answered"}:
        reminder.status = "calling"
        reminder.last_call_status = normalized
    elif normalized == "queued":
        reminder.status = "calling"
        reminder.last_call_status = normalized
    reminder.updated_at = datetime.now(timezone.utc)
    db.add(reminder)
    db.commit()


def reminder_to_item(reminder: Reminder) -> dict[str, object]:
    return {
        "id": reminder.id,
        "title": reminder.title,
        "notes": reminder.notes,
        "reminder_at": reminder.reminder_at,
        "timezone": reminder.timezone,
        "phone_number": reminder.phone_number,
        "status": reminder.status,
        "retry_count": reminder.retry_count,
        "max_retry_attempts": reminder.max_retry_attempts,
        "next_retry_at": reminder.next_retry_at,
        "last_call_status": reminder.last_call_status,
        "provider": reminder.provider,
        "provider_call_id": reminder.provider_call_id,
        "called_at": reminder.called_at,
        "last_error": reminder.last_error,
        "completed_manually_at": reminder.completed_manually_at,
        "snoozed_until": reminder.snoozed_until,
        "created_at": reminder.created_at,
        "updated_at": reminder.updated_at,
    }


def user_has_active_phone(user: User) -> bool:
    phone = (user.phone_number or "").strip()
    return bool(phone and phone.startswith("+") and len(phone) >= 8)


def run_due_reminder_calls() -> None:
    from app.database.session import SessionLocal
    from app.models.user import User
    from app.config import settings
    from app.services.recurring_reminder_service import generate_due_occurrences

    if not settings.reminder_calls_enabled:
        return
    db = SessionLocal()
    try:
        now_utc = datetime.now(timezone.utc)
        generate_due_occurrences(db, now_utc=now_utc)
        due_reminders = get_retry_due_reminders(db, now_utc)
        for reminder in due_reminders:
            user = db.query(User).filter(User.id == reminder.user_id).first()
            if user is None:
                continue
            try:
                if not claim_reminder_for_call(db, reminder):
                    continue
                start_reminder_call(db, reminder, user)
                logger.info("Reminder call started reminder_id=%s user_id=%s", reminder.id, user.id)
            except Exception as exc:
                db.rollback()
                mark_reminder_failed(db, reminder, str(exc))
                logger.error("Reminder call failed reminder_id=%s user_id=%s error=%s", reminder.id, user.id, str(exc))
    finally:
        db.close()


def snooze_reminder(db: Session, user: User, reminder_id: int, minutes: int) -> Reminder:
    reminder = get_reminder(db, user, reminder_id)
    snooze_minutes = max(1, min(int(minutes), 24 * 60))
    now_utc = datetime.now(timezone.utc)
    reminder.status = "snoozed"
    reminder.snoozed_until = now_utc + timedelta(minutes=snooze_minutes)
    reminder.next_retry_at = reminder.snoozed_until
    reminder.updated_at = now_utc
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


def mark_reminder_done(db: Session, user: User, reminder_id: int) -> Reminder:
    reminder = get_reminder(db, user, reminder_id)
    now_utc = datetime.now(timezone.utc)
    reminder.status = "completed"
    reminder.completed_manually_at = now_utc
    reminder.called_at = reminder.called_at or now_utc
    reminder.next_retry_at = None
    reminder.snoozed_until = None
    reminder.last_error = None
    reminder.last_call_status = reminder.last_call_status or "completed"
    reminder.updated_at = now_utc
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


def call_again_reminder(db: Session, user: User, reminder_id: int) -> Reminder:
    reminder = get_reminder(db, user, reminder_id)
    if reminder.status not in {"missed", "failed", "retry_scheduled", "snoozed"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reminder cannot be called again")
    previous_status = reminder.status
    now_utc = datetime.now(timezone.utc)
    reminder.status = "scheduled"
    if previous_status == "missed":
        reminder.retry_count = 0
    reminder.next_retry_at = None
    reminder.snoozed_until = None
    reminder.last_error = None
    reminder.updated_at = now_utc
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    try:
        if not user_has_active_phone(user):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone number is required")
        claim_reminder_for_call(db, reminder)
        start_reminder_call(db, reminder, user)
    except Exception:
        db.rollback()
        reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
        if reminder:
            reminder.status = previous_status if previous_status in {"missed", "failed", "retry_scheduled", "snoozed"} else "scheduled"
            reminder.updated_at = datetime.now(timezone.utc)
            db.add(reminder)
            db.commit()
            db.refresh(reminder)
        raise
    return reminder


def mark_reminder_missed(db: Session, reminder: Reminder) -> Reminder:
    reminder.status = "missed"
    reminder.next_retry_at = None
    reminder.last_error = "missed after max retry attempts"
    reminder.updated_at = datetime.now(timezone.utc)
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder
