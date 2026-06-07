from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
import logging
import re
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session
from twilio.twiml.voice_response import Gather, VoiceResponse

from app.config import settings
from app.models.email_summary import EmailSummary
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.reminder import Reminder
from app.models.user import User
from app.models.voice_reminder_session import VoiceReminderSession
from app.services.reminder_service import create_reminder
from app.services.voice_email_lookup_service import resolve_email_reference_for_call
from app.services.voice_intent_service import (
    INTENT_CANCEL_REMINDER_CREATE,
    INTENT_CONFIRM_CREATE_REMINDER,
    INTENT_DETAIL_EMAIL,
    INTENT_END_CALL,
    INTENT_START_REMINDER_CREATE,
    INTENT_UNKNOWN,
    LOOKUP_FIRST,
    LOOKUP_LAST,
    LOOKUP_LATEST,
    LOOKUP_UNKNOWN,
    ParsedVoiceIntent,
)

logger = logging.getLogger(__name__)
GATHER_TIMEOUT_SECONDS = 8


def _voice_base_url() -> str:
    return settings.public_backend_url.rstrip("/")


def build_slow_say(response: VoiceResponse | Gather, text: str) -> None:
    spoken_text = str(text or "").strip()
    if spoken_text:
        response.say(spoken_text, voice="alice", language="en-US")


def build_gather_twiml(call_log_id: int, prompt_text: str, followup_text: str | None = None) -> str:
    response = VoiceResponse()
    gather = Gather(
        input="speech dtmf",
        action=f"{_voice_base_url()}/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
        method="POST",
        speech_timeout="auto",
        timeout=max(GATHER_TIMEOUT_SECONDS, 10),
        action_on_empty_result=True,
        language="en-IN",
        hints=(
            "explain email number one, explain email one, remind me about this email in two minutes, "
            "remind me about this email in 2 minutes, yes save it, save it, yes create it, no cancel, "
            "repeat summary, reply to this email"
        ),
    )
    build_slow_say(gather, prompt_text)
    if followup_text:
        gather.pause(length=1)
        build_slow_say(gather, followup_text)
    response.append(gather)
    return str(response)


def build_end_call_twiml() -> str:
    response = VoiceResponse()
    build_slow_say(response, "Okay, ending the call. Have a good day.")
    response.hangup()
    return str(response)


@dataclass(slots=True)
class ReminderDraft:
    title: str
    notes: str | None
    reminder_date: str | None = None
    reminder_time: str | None = None
    timezone: str | None = None
    phone_number: str | None = None
    reminder_at: datetime | None = None


def normalize_reminder_text(text: str | None) -> str:
    normalized = (text or "").strip().lower()
    normalized = re.sub(r"\b(?:2|to|too)\s+minutes?\b", "two minutes", normalized)
    normalized = re.sub(r"\b(?:1|one)\s+minutes?\b", "one minute", normalized)
    normalized = re.sub(r"\b(?:after|in)\s+two minutes?\b", "in two minutes", normalized)
    normalized = re.sub(r"\b(?:after|in)\s+one minute\b", "in one minute", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _active_session(db: Session, user_id: int, call_log_id: int) -> VoiceReminderSession | None:
    try:
        return (
            db.query(VoiceReminderSession)
            .filter(
                VoiceReminderSession.user_id == user_id,
                VoiceReminderSession.mail_call_log_id == call_log_id,
                VoiceReminderSession.status.in_(["awaiting_details", "awaiting_confirmation"]),
            )
            .order_by(VoiceReminderSession.id.desc())
            .first()
        )
    except (OperationalError, ProgrammingError):
        db.rollback()
        return None


def get_active_reminder_session(db: Session, user: User, call_log: MailSummaryCallLog) -> VoiceReminderSession | None:
    return _active_session(db, user.id, call_log.id)


def start_reminder_session(
    db: Session,
    user: User,
    call_log: MailSummaryCallLog,
    summary: EmailSummary | None,
    target_email_reference: int | None = None,
    reminder_datetime: datetime | None = None,
    reminder_text: str | None = None,
) -> VoiceReminderSession:
    title = f"Check email: {summary.subject or 'No subject'}" if summary else "General reminder"
    notes_parts: list[str] = []
    if summary:
        sender = summary.sender or (summary.email_message.sender if summary.email_message else None) or "Unknown sender"
        subject = summary.subject or "No subject"
        notes_parts.append(f"From: {sender}.")
        notes_parts.append(f"Subject: {subject}.")
        if summary.short_summary:
            notes_parts.append(f"Summary: {summary.short_summary}.")
        elif summary.detailed_summary:
            notes_parts.append(f"Summary: {summary.detailed_summary}.")
    notes = " ".join(notes_parts) if notes_parts else reminder_text
    session = VoiceReminderSession(
        user_id=user.id,
        mail_call_log_id=call_log.id,
        email_message_id=summary.email_message_id if summary else None,
        email_summary_id=summary.id if summary else None,
        target_email_reference=target_email_reference,
        reminder_title=title,
        reminder_notes=notes,
        reminder_at=reminder_datetime,
        reminder_timezone=user.timezone or "UTC",
        reminder_phone_number=user.phone_number,
        status="awaiting_confirmation" if reminder_datetime else "awaiting_details",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    if reminder_text and not session.reminder_notes:
        session.reminder_notes = reminder_text
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def update_reminder_details(
    db: Session,
    session: VoiceReminderSession,
    reminder_datetime: datetime,
    reminder_timezone: str | None = None,
) -> VoiceReminderSession:
    session.reminder_at = reminder_datetime
    if reminder_timezone:
        session.reminder_timezone = reminder_timezone
    session.status = "awaiting_confirmation"
    session.updated_at = datetime.now(timezone.utc)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def cancel_reminder_session(db: Session, session: VoiceReminderSession, reason: str | None = None) -> VoiceReminderSession:
    session.status = "cancelled"
    session.last_error = reason
    session.updated_at = datetime.now(timezone.utc)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _build_create_payload(user: User, session: VoiceReminderSession):
    if session.reminder_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reminder time is missing")
    reminder_zone = session.reminder_timezone or user.timezone or "UTC"
    try:
        local_zone = ZoneInfo(reminder_zone)
    except Exception:
        local_zone = timezone.utc
    local_dt = session.reminder_at.astimezone(timezone.utc).astimezone(local_zone)
    return type(
        "_ReminderPayload",
        (),
        {
            "title": session.reminder_title or "Email follow-up reminder",
            "notes": session.reminder_notes,
            "reminder_date": local_dt.strftime("%Y-%m-%d"),
            "reminder_time": local_dt.strftime("%H:%M"),
            "timezone": reminder_zone,
            "phone_number": session.reminder_phone_number,
        },
    )()


def send_reminder_creation(db: Session, user: User, session: VoiceReminderSession) -> Reminder:
    reminder = create_reminder(db, user, _build_create_payload(user, session))
    created = db.query(Reminder).filter(Reminder.id == reminder["id"]).first()
    if created is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Reminder could not be created")
    session.status = "created"
    session.created_reminder_id = created.id
    session.updated_at = datetime.now(timezone.utc)
    db.add(session)
    db.commit()
    db.refresh(session)
    return created


def build_reminder_details_prompt(call_log_id: int) -> str:
    return build_gather_twiml(
        call_log_id,
        "What date and time should I set the reminder for?",
        "You can say something like tomorrow at 3 pm, or Monday at 10 am.",
    )


def build_reminder_confirmation_twiml(call_log_id: int, summary_text: str) -> str:
    return build_gather_twiml(
        call_log_id,
        summary_text,
        "Say yes save it, or press 1 to save. Say no cancel, or press 2 to cancel.",
    )


def build_reminder_created_twiml() -> str:
    response = VoiceResponse()
    build_slow_say(response, "Your reminder has been created.")
    response.hangup()
    return str(response)


def build_reminder_cancellation_twiml() -> str:
    response = VoiceResponse()
    build_slow_say(response, "Okay, I cancelled the reminder creation.")
    response.hangup()
    return str(response)


def _parse_iso_datetime(candidate: str | None) -> datetime | None:
    if not candidate:
        return None
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _parse_relative_reminder_time(text: str, base: datetime | None = None) -> datetime | None:
    from dateparser import parse as dateparse

    base_dt = base or datetime.now(timezone.utc)
    parsed = dateparse(
        text,
        settings={
            "RETURN_AS_TIMEZONE_AWARE": True,
            "TIMEZONE": "UTC",
            "TO_TIMEZONE": "UTC",
            "RELATIVE_BASE": base_dt,
        },
    )
    return parsed.astimezone(timezone.utc) if parsed else None


def parse_reminder_datetime(transcript: str | None) -> datetime | None:
    text = normalize_reminder_text(transcript)
    if not text:
        return None
    parsed = _parse_iso_datetime(text)
    if parsed is not None:
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    try:
        from dateparser.search import search_dates

        matches = search_dates(
            text,
            settings={
                "RETURN_AS_TIMEZONE_AWARE": True,
                "TIMEZONE": "UTC",
                "TO_TIMEZONE": "UTC",
            },
        )
        if matches:
            for _, candidate in reversed(matches):
                if candidate is not None:
                    return candidate.astimezone(timezone.utc) if candidate.tzinfo else candidate.replace(tzinfo=timezone.utc)
    except Exception:
        logger.exception("Failed to search reminder datetime from %r", text)
    try:
        return _parse_relative_reminder_time(text)
    except Exception:
        logger.exception("Failed to parse reminder datetime from %r", text)
        return None


def reminder_session_to_dict(session: VoiceReminderSession) -> dict[str, object]:
    return {
        "id": session.id,
        "status": session.status,
        "reminder_title": session.reminder_title,
        "reminder_notes": session.reminder_notes,
        "reminder_at": session.reminder_at,
        "reminder_timezone": session.reminder_timezone,
        "reminder_phone_number": session.reminder_phone_number,
        "created_reminder_id": session.created_reminder_id,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


def _safe_user_reply_prompt() -> str:
    return "Please say yes to create the reminder, or no to cancel."


def process_reminder_session_webhook(
    db: Session,
    call_log: MailSummaryCallLog,
    session: VoiceReminderSession,
    transcript: str | None,
    confidence: str | None,
    parsed_intent: ParsedVoiceIntent,
) -> str:
    text = (transcript or "").strip()
    normalized = text.lower()
    digits = None
    try:
        digits = getattr(parsed_intent, "digits", None)
    except Exception:
        digits = None
    intent = parsed_intent.intent
    if digits == "2" or intent in {INTENT_CANCEL_REMINDER_CREATE, INTENT_END_CALL} or normalized in {"no", "cancel", "no cancel", "cancel reminder"}:
        cancel_reminder_session(db, session, "user cancelled reminder creation")
        return build_reminder_cancellation_twiml()
    if digits == "1" or intent == INTENT_CONFIRM_CREATE_REMINDER or normalized in {"yes", "yeah", "yep", "ok", "okay", "save", "save it", "save this", "yes save", "yes save it", "yes create it", "create it", "create", "confirm", "okay save it", "ok save it", "yeah save it", "yes please", "do it"} or normalized.startswith("yes "):
        created = send_reminder_creation(db, call_log.user, session)
        return build_reminder_created_twiml()
    if session.status == "awaiting_details":
        parsed = parse_reminder_datetime(text)
        if parsed is None:
            return build_reminder_details_prompt(call_log.id)
        update_reminder_details(db, session, parsed, session.reminder_timezone or call_log.user.timezone or "UTC")
        local_dt = parsed.astimezone(timezone.utc)
        summary = f"I will create this reminder: {session.reminder_title or 'General reminder'} at {local_dt.strftime('%A %B %d at %I:%M %p UTC')}. " + _safe_user_reply_prompt()
        return build_reminder_confirmation_twiml(call_log.id, summary)
    if session.status == "awaiting_confirmation":
        summary = (
            f"I will create this reminder: {session.reminder_title or 'General reminder'} "
            f"at {session.reminder_at.astimezone(timezone.utc).strftime('%A %B %d at %I:%M %p UTC') if session.reminder_at else 'the requested time'}. "
            "Say yes save it, or press 1 to save. Say no cancel, or press 2 to cancel."
        )
        return build_reminder_confirmation_twiml(call_log.id, summary)
    return build_reminder_details_prompt(call_log.id)
