from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.email_message import EmailMessage
from app.models.email_summary import EmailSummary
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.user import User
from app.services.email_summarization_service import summary_to_item

MAX_MAIL_SUMMARY_CALLS_PER_DAY = 3


def _user_timezone(user: User) -> ZoneInfo:
    return ZoneInfo(user.timezone or "UTC")


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


def _counted_mail_summary_calls_query(db: Session, user_id: int, call_date):
    return (
        db.query(MailSummaryCallLog)
        .filter(
            MailSummaryCallLog.user_id == user_id,
            MailSummaryCallLog.call_type == "mail_summary",
            MailSummaryCallLog.call_date == call_date,
        )
    )


def get_mail_call_count_today(db: Session, user: User) -> dict[str, object]:
    today, start_utc, end_utc = _today_window_utc(user)
    used_calls_today = _counted_mail_summary_calls_query(db, user.id, today).count()
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
                f"Email {index}. From {summary.sender or 'Unknown sender'}. Subject: {summary.subject or 'No subject'}.",
                f"Summary: {summary.short_summary or 'Summary not available.'}",
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
