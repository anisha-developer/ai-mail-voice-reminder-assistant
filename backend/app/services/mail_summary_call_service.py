from __future__ import annotations

import json
import re
from email.utils import parseaddr
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.email_message import EmailMessage
from app.models.email_summary import EmailSummary
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.user import User
from app.models.user_call_preference import UserCallPreference
from app.core.timezone import normalize_timezone_name
from app.services.email_summarization_service import summary_to_item

MAX_MAIL_SUMMARY_CALLS_PER_DAY = 3
DEFAULT_SLOT_TIMES = ("09:00", "13:00", "19:00")
EMAIL_ADDRESS_RE = re.compile(r"(?<![\w.-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _user_timezone(user: User) -> ZoneInfo:
    return ZoneInfo(normalize_timezone_name(user.timezone, "UTC"))


def _user_local_now(user: User) -> datetime:
    return datetime.now(_user_timezone(user))


def _today_window_utc(user: User) -> tuple[date, datetime, datetime]:
    local_now = _user_local_now(user)
    today = local_now.date()
    start_local = datetime.combine(today, datetime.min.time(), tzinfo=_user_timezone(user))
    end_local = start_local + timedelta(days=1)
    return today, start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _summary_ids_payload(summary_ids: list[int]) -> str:
    return json.dumps(summary_ids)


def _parse_summary_ids(payload: str | None) -> list[int]:
    if not payload:
        return []
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [int(item) for item in data]
    return []


def _spoken_sender_name(sender: str | None) -> str:
    raw = (sender or "").strip()
    if not raw:
        return "Unknown sender"
    display_name, _ = parseaddr(raw)
    if display_name.strip():
        return display_name.strip()
    if "<" in raw and ">" in raw:
        prefix = raw.split("<", 1)[0].strip()
        if prefix:
            return prefix
    return "Unknown sender"


def _spoken_subject(subject: str | None) -> str:
    text = (subject or "No subject").strip() or "No subject"
    for prefix in ("re:", "fwd:"):
        if text.lower().startswith(prefix):
            text = text[len(prefix):].strip()
    return text or "No subject"


def _shorten_voice_text(text: str, max_sentences: int = 2, max_chars: int = 320) -> str:
    cleaned = EMAIL_ADDRESS_RE.sub("the sender", (text or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]
    if sentences:
        shortened = " ".join(sentences[:max_sentences]).strip()
    else:
        shortened = cleaned
    if len(shortened) > max_chars:
        shortened = shortened[:max_chars].rsplit(" ", 1)[0].rstrip(".,;:")
    return shortened.strip()


def _voice_summary_text(summary: EmailSummary) -> str:
    detailed = (summary.detailed_summary or "").strip()
    short = (summary.short_summary or "").strip()
    source_text = detailed or short
    if not source_text:
        subject = _spoken_subject(summary.subject)
        return f"Email received about {subject}. It may need review."

    if detailed:
        source_text = _shorten_voice_text(source_text, max_sentences=2, max_chars=320)
    else:
        source_text = EMAIL_ADDRESS_RE.sub("the sender", source_text)
        source_text = re.sub(r"\s+", " ", source_text).strip()

    if source_text.lower().startswith("this email is from ") or source_text.lower().startswith("indha email "):
        subject = _spoken_subject(summary.subject)
        return f"Email received about {subject}. It may need review based on the subject and sender."

    return source_text or f"Email received about {_spoken_subject(summary.subject)}. It may need review."


def _current_slot_times(db: Session, user_id: int) -> set[str]:
    prefs = db.query(UserCallPreference).filter(UserCallPreference.user_id == user_id).first()
    if prefs is None:
        return set(DEFAULT_SLOT_TIMES)
    slots = []
    for slot_time, enabled in (
        (prefs.call_slot_1_time, prefs.call_slot_1_enabled),
        (prefs.call_slot_2_time, prefs.call_slot_2_enabled),
        (prefs.call_slot_3_time, prefs.call_slot_3_enabled),
    ):
        if enabled and slot_time:
            slots.append(str(slot_time)[:5])
    return set(slots or DEFAULT_SLOT_TIMES)


def _counted_mail_summary_calls_query(db: Session, user_id: int, call_date):
    return (
        db.query(MailSummaryCallLog.call_time)
        .filter(
            MailSummaryCallLog.user_id == user_id,
            MailSummaryCallLog.call_type == "mail_summary",
            MailSummaryCallLog.call_date == call_date,
            MailSummaryCallLog.delivery_status == "delivered",
        )
    )


def get_mail_call_count_today(db: Session, user: User) -> dict[str, object]:
    today, start_utc, end_utc = _today_window_utc(user)
    slot_times = _current_slot_times(db, user.id)
    used_calls_today = len(
        {
            call_time.strftime("%H:%M")
            for (call_time,) in _counted_mail_summary_calls_query(db, user.id, today).all()
            if call_time is not None and call_time.strftime("%H:%M") in slot_times
        }
    )
    todays_summary_query = _todays_summaries_query(db, user.id, start_utc, end_utc)
    total_today_summaries = todays_summary_query.count()
    pending_today_summaries = _pending_today_summaries_query(db, user.id, start_utc, end_utc).count()
    return {
        "max_calls_per_day": MAX_MAIL_SUMMARY_CALLS_PER_DAY,
        "used_calls_today": used_calls_today,
        "remaining_calls_today": max(0, MAX_MAIL_SUMMARY_CALLS_PER_DAY - used_calls_today),
        "date": today,
        "total_summaries_in_database": db.query(EmailSummary).filter(EmailSummary.user_id == user.id).count(),
        "today_summaries_count": total_today_summaries,
        "pending_today_summaries_count": pending_today_summaries,
    }


def _todays_summaries_query(db: Session, user_id: int, start_utc: datetime, end_utc: datetime):
    return (
        db.query(EmailSummary)
        .join(EmailMessage, EmailMessage.id == EmailSummary.email_message_id)
        .filter(
            EmailSummary.user_id == user_id,
            EmailSummary.summary_status == "completed",
            EmailMessage.user_id == user_id,
            EmailMessage.is_in_inbox.is_(True),
            EmailMessage.received_at.is_not(None),
            EmailMessage.received_at >= start_utc,
            EmailMessage.received_at < end_utc,
        )
        .order_by(EmailMessage.received_at.desc(), EmailSummary.id.asc())
    )


def _pending_today_summaries_query(db: Session, user_id: int, start_utc: datetime, end_utc: datetime):
    return (
        _todays_summaries_query(db, user_id, start_utc, end_utc)
        .filter(
            EmailSummary.is_delivered_in_mail_call.is_(False),
            EmailSummary.mail_call_log_id.is_(None),
        )
    )


def list_todays_summaries(db: Session, user: User) -> list[EmailSummary]:
    _, start_utc, end_utc = _today_window_utc(user)
    return _todays_summaries_query(db, user.id, start_utc, end_utc).all()


def list_pending_today_summaries(db: Session, user: User) -> list[EmailSummary]:
    _, start_utc, end_utc = _today_window_utc(user)
    return _pending_today_summaries_query(db, user.id, start_utc, end_utc).all()


def _script_for_summaries(summaries: list[EmailSummary]) -> str:
    intro = f"Hello. You received {len(summaries)} emails today."
    parts = [intro, ""]
    for index, summary in enumerate(summaries, start=1):
        parts.extend(
            [
                f"Email {index}. From {_spoken_sender_name(summary.sender)}. Subject: {_spoken_subject(summary.subject)}.",
                f"Summary: {_voice_summary_text(summary)}",
                "",
            ]
        )
    parts.append(
        "I have read today's email summaries. Is there any important mail you want me to explain in detail? "
        "You can say email number one, email number two, or say no to end the call."
    )
    return "\n".join(parts).strip()


def prepare_mail_summary_call(db: Session, user: User, include_delivered: bool = False) -> dict[str, object]:
    counts = get_mail_call_count_today(db, user)
    if counts["used_calls_today"] >= MAX_MAIL_SUMMARY_CALLS_PER_DAY:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Daily mail summary call limit reached")

    pending_summaries = list_todays_summaries(db, user) if include_delivered else list_pending_today_summaries(db, user)
    if not pending_summaries:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No emails received today.")

    local_now = _user_local_now(user)
    summary_ids = [summary.id for summary in pending_summaries]
    call_log = MailSummaryCallLog(
        user_id=user.id,
        call_type="mail_summary",
        call_status="prepared",
        call_date=local_now.date(),
        call_time=local_now.time().replace(second=0, microsecond=0),
        summary_count=len(pending_summaries),
        script_text=_script_for_summaries(pending_summaries),
        delivery_status="pending",
        delivered_summary_ids=_summary_ids_payload(summary_ids),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(call_log)
    db.flush()

    for summary in pending_summaries:
        summary.mail_call_log_id = call_log.id
        summary.updated_at = datetime.now(timezone.utc)
        db.add(summary)

    db.commit()
    db.refresh(call_log)

    updated_counts = get_mail_call_count_today(db, user)
    return {
        "call_log_id": call_log.id,
        "summary_count": call_log.summary_count,
        "script_text": call_log.script_text or "",
        "today_summaries_count": counts["today_summaries_count"],
        "pending_today_summaries_count": len(pending_summaries),
        "used_calls_today": updated_counts["used_calls_today"],
        "remaining_calls_today": updated_counts["remaining_calls_today"],
    }


def mark_mail_call_delivered(db: Session, user: User, call_log_id: int) -> dict[str, object]:
    call_log = (
        db.query(MailSummaryCallLog)
        .filter(
            MailSummaryCallLog.id == call_log_id,
            MailSummaryCallLog.user_id == user.id,
            MailSummaryCallLog.call_type == "mail_summary",
        )
        .first()
    )
    if call_log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid call log ID")
    if call_log.delivery_status == "delivered":
        return {
            "success": True,
            "call_log_id": call_log.id,
            "delivered_summary_count": call_log.summary_count,
            "message": "Mail summary call already marked as delivered.",
        }

    summary_ids = _parse_summary_ids(call_log.delivered_summary_ids)
    summaries = []
    if summary_ids:
        summaries = (
            db.query(EmailSummary)
            .filter(
                EmailSummary.user_id == user.id,
                EmailSummary.id.in_(summary_ids),
            )
            .all()
        )
    delivered_at = datetime.now(timezone.utc)
    delivered_count = 0
    for summary in summaries:
        if not summary.is_delivered_in_mail_call:
            summary.is_delivered_in_mail_call = True
            summary.delivered_at = delivered_at
            summary.mail_call_log_id = call_log.id
            summary.updated_at = delivered_at
            db.add(summary)
            delivered_count += 1

    call_log.call_status = "delivered"
    call_log.delivery_status = "delivered"
    call_log.updated_at = delivered_at
    db.add(call_log)
    db.commit()

    return {
        "success": True,
        "call_log_id": call_log.id,
        "delivered_summary_count": delivered_count,
        "message": "Mail summary call marked as delivered.",
    }


def list_mail_call_history(db: Session, user: User) -> list[MailSummaryCallLog]:
    return (
        db.query(MailSummaryCallLog)
        .filter(
            MailSummaryCallLog.user_id == user.id,
            MailSummaryCallLog.call_type == "mail_summary",
        )
        .order_by(MailSummaryCallLog.created_at.desc(), MailSummaryCallLog.id.desc())
        .all()
    )


def mail_call_to_item(call_log: MailSummaryCallLog) -> dict[str, object]:
    return {
        "id": call_log.id,
        "call_type": call_log.call_type,
        "call_status": call_log.call_status,
        "call_date": call_log.call_date,
        "call_time": call_log.call_time,
        "summary_count": call_log.summary_count,
        "script_text": call_log.script_text,
        "provider": call_log.provider,
        "provider_call_id": call_log.provider_call_id,
        "to_phone_number": call_log.to_phone_number,
        "from_phone_number": call_log.from_phone_number,
        "call_started_at": call_log.call_started_at,
        "call_completed_at": call_log.call_completed_at,
        "call_duration_seconds": call_log.call_duration_seconds,
        "provider_status": call_log.provider_status,
        "provider_error_message": call_log.provider_error_message,
        "delivery_status": call_log.delivery_status,
        "delivered_summary_ids": _parse_summary_ids(call_log.delivered_summary_ids),
        "failure_reason": call_log.failure_reason,
        "created_at": call_log.created_at,
        "updated_at": call_log.updated_at,
    }


def pending_summaries_payload(db: Session, user: User) -> dict[str, object]:
    summaries = list_pending_today_summaries(db, user)
    todays_summaries = list_todays_summaries(db, user)
    counts = get_mail_call_count_today(db, user)
    return {
        "pending_count": len(summaries),
        "pending_today_count": len(summaries),
        "today_summaries_count": len(todays_summaries),
        "total_summaries_in_database": counts["total_summaries_in_database"],
        "summaries": [summary_to_item(summary) for summary in summaries],
    }
