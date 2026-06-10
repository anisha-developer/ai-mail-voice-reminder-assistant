from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from twilio.rest import Client
from twilio.twiml.voice_response import Gather, VoiceResponse

from app.config import settings
from app.models.email_summary import EmailSummary
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.user import User
from app.models.voice_call_interaction import VoiceCallInteraction
from app.models.voice_reply_session import VoiceReplySession
from app.services.voice_reminder_service import (
    build_end_call_twiml as build_reminder_end_call_twiml,
    build_reminder_cancellation_twiml,
    build_reminder_created_twiml,
    build_reminder_confirmation_twiml,
    build_reminder_details_prompt,
    get_active_reminder_session,
    parse_reminder_datetime,
    process_reminder_session_webhook,
    start_reminder_session,
    update_reminder_details,
)
from app.services.mail_summary_call_service import mark_mail_call_delivered
from app.services.gmail_reply_service import cancel_reply, get_active_reply_session, send_reply, start_reply_session, update_reply_body
from app.services.elevenlabs_service import start_mail_summary_call_with_elevenlabs
from app.services.voice_email_lookup_service import get_last_explained_email_for_call, resolve_email_reference_for_call
from app.services.voice_intent_service import (
    INTENT_DETAIL_EMAIL,
    INTENT_END_CALL,
    INTENT_CREATE_RECURRING_REMINDER,
    INTENT_HELP,
    INTENT_IMPORTANT_CHECK,
    INTENT_CANCEL_REPLY,
    INTENT_CAPTURE_REPLY_BODY,
    INTENT_CONFIRM_SEND_REPLY,
    INTENT_EDIT_REPLY,
    INTENT_START_EMAIL_REPLY,
    INTENT_START_REMINDER_CREATE,
    INTENT_CAPTURE_REMINDER_DATETIME,
    INTENT_CONFIRM_CREATE_REMINDER,
    INTENT_CANCEL_REMINDER_CREATE,
    INTENT_REPEAT_SUMMARY,
    INTENT_TODAY_SUMMARY,
    INTENT_UNKNOWN,
    LOOKUP_FIRST,
    LOOKUP_LAST,
    LOOKUP_LATEST,
    LOOKUP_UNKNOWN,
    ParsedVoiceIntent,
    parse_voice_intent,
)
from app.services.smart_voice_intent_service import (
    INTENT_NEXT_EMAIL,
    INTENT_PREVIOUS_EMAIL,
    resolve_smart_voice_intent,
)

VOICE_PROVIDER_TWILIO = "twilio"
TWILIO_TERMINAL_FAILURE_STATES = {"failed", "busy", "no-answer", "canceled"}
TWILIO_COMPLETED_STATE = "completed"
MAX_TWIML_SUMMARY_ITEMS = 5
GATHER_TIMEOUT_SECONDS = 8
MAX_DETAIL_REQUESTS = 2
MAX_REPEAT_REQUESTS = 1
MAX_UNKNOWN_REQUESTS = 2
MAX_SILENCE_REQUESTS = 1

logger = logging.getLogger(__name__)


def _recurring_payload_is_ready(smart_resolution) -> bool:
    repeat_type = getattr(smart_resolution, "repeat_type", None)
    if repeat_type in {"daily", "weekdays"}:
        return bool(getattr(smart_resolution, "time_of_day", None))
    if repeat_type in {"weekly", "custom_days"}:
        return bool(getattr(smart_resolution, "days_of_week", None) and getattr(smart_resolution, "time_of_day", None))
    if repeat_type == "monthly":
        return bool(getattr(smart_resolution, "day_of_month", None) and getattr(smart_resolution, "time_of_day", None))
    if repeat_type == "custom_interval":
        return bool(getattr(smart_resolution, "interval_value", None) and getattr(smart_resolution, "interval_unit", None))
    return False


def _recurring_confirmation_text(session: VoiceReminderSession, reminder_dt: datetime | None = None) -> str:
    title = session.reminder_title or "Recurring reminder"
    parts = [f"I will create a recurring reminder titled {title}."]
    repeat_type = session.repeat_type or "recurring"
    if repeat_type == "daily":
        parts.append(f"It will repeat every day at {session.time_of_day or 'the requested time'}.")
    elif repeat_type == "weekdays":
        parts.append(f"It will repeat on weekdays at {session.time_of_day or 'the requested time'}.")
    elif repeat_type in {"weekly", "custom_days"}:
        days = ", ".join((json.loads(session.days_of_week) if session.days_of_week else []) or [])
        parts.append(f"It will repeat on {days or 'the selected days'} at {session.time_of_day or 'the requested time'}.")
    elif repeat_type == "monthly":
        parts.append(f"It will repeat on day {session.day_of_month or 'the selected day'} of each month at {session.time_of_day or 'the requested time'}.")
    elif repeat_type == "custom_interval":
        parts.append(
            f"It will repeat every {session.interval_value or 1} {session.interval_unit or 'days'}."
        )
    elif reminder_dt is not None:
        parts.append(
            f"It will start on {reminder_dt.astimezone(timezone.utc).strftime('%A %B %d at %I:%M %p UTC')}."
        )
    parts.append("Say yes save it, or press 1 to save. Say no cancel, or press 2 to cancel.")
    return " ".join(parts)

def _require_twilio_config() -> None:
    missing = []
    if not settings.twilio_account_sid:
        missing.append("TWILIO_ACCOUNT_SID")
    if not settings.twilio_auth_token:
        missing.append("TWILIO_AUTH_TOKEN")
    if not settings.twilio_from_phone:
        missing.append("TWILIO_FROM_PHONE")
    if not settings.public_backend_url:
        missing.append("PUBLIC_BACKEND_URL")
    if missing:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Missing voice provider configuration: {', '.join(missing)}",
        )


def _validate_user_phone(user: User) -> str:
    phone = (user.phone_number or "").strip()
    if not phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has no phone number")
    if not phone.startswith("+") or len(phone) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone number")
    return phone


def _twilio_client() -> Client:
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def _voice_base_url() -> str:
    return settings.public_backend_url.rstrip("/")


def get_mail_call_for_user(db: Session, user: User, call_log_id: int) -> MailSummaryCallLog:
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call log not found")
    return call_log


def _get_mail_call_by_provider_call_id(db: Session, provider_call_id: str) -> MailSummaryCallLog:
    call_log = db.query(MailSummaryCallLog).filter(MailSummaryCallLog.provider_call_id == provider_call_id).first()
    if call_log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Matching provider call not found")
    return call_log


def start_mail_summary_voice_call(db: Session, user: User, call_log_id: int) -> dict[str, str]:
    to_phone = _validate_user_phone(user)
    call_log = get_mail_call_for_user(db, user, call_log_id)

    if call_log.call_status != "prepared":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Call log is not prepared")
    if call_log.delivery_status == "delivered":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Call has already been delivered")
    if not call_log.script_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Prepared call script is missing")

    provider = (settings.voice_agent_provider or VOICE_PROVIDER_TWILIO).strip().lower()
    if provider == "elevenlabs":
        try:
            elevenlabs_result = start_mail_summary_call_with_elevenlabs(db, user, call_log)
        except HTTPException as exc:
            logger.warning(
                "ElevenLabs provider unavailable for mail summary call_log_id=%s; falling back to Twilio: %s",
                call_log.id,
                exc.detail,
            )
        else:
            provider_call_id = elevenlabs_result.get("provider_call_id") or f"elevenlabs-{call_log.id}"
            provider_status = elevenlabs_result.get("status") or "queued"
            call_log.provider = "elevenlabs"
            call_log.provider_call_id = provider_call_id
            call_log.to_phone_number = to_phone
            call_log.from_phone_number = None
            call_log.provider_status = provider_status
            call_log.call_status = provider_status.replace("-", "_")
            call_log.delivery_status = "pending"
            call_log.updated_at = datetime.now(timezone.utc)
            db.add(call_log)
            db.commit()
            return {
                "call_log_id": call_log.id,
                "provider": "elevenlabs",
                "provider_call_id": provider_call_id,
                "call_status": call_log.call_status,
            }

    _require_twilio_config()
    client = _twilio_client()
    twiml_url = f"{_voice_base_url()}/voice/mail-calls/{call_log.id}/twiml"
    status_callback = f"{_voice_base_url()}/voice/webhooks/twilio/status"

    try:
        provider_call = client.calls.create(
            to=to_phone,
            from_=settings.twilio_from_phone,
            url=twiml_url,
            method="GET",
            status_callback=status_callback,
            status_callback_method="POST",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
        )
    except Exception as exc:
        call_log.call_status = "failed"
        call_log.delivery_status = "failed"
        call_log.provider = VOICE_PROVIDER_TWILIO
        call_log.to_phone_number = to_phone
        call_log.from_phone_number = settings.twilio_from_phone
        call_log.failure_reason = "Twilio API failure"
        call_log.provider_error_message = str(exc)
        call_log.updated_at = datetime.now(timezone.utc)
        db.add(call_log)
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Twilio API failure") from exc

    call_log.provider = VOICE_PROVIDER_TWILIO
    call_log.provider_call_id = provider_call.sid
    call_log.to_phone_number = to_phone
    call_log.from_phone_number = settings.twilio_from_phone
    provider_status = provider_call.status or "queued"
    call_log.provider_status = provider_status
    call_log.call_status = provider_status.replace("-", "_")
    call_log.updated_at = datetime.now(timezone.utc)
    if provider_status in {"queued", "initiated"}:
        call_log.call_started_at = datetime.now(timezone.utc)
    db.add(call_log)
    db.commit()

    return {
        "call_log_id": call_log.id,
        "provider": VOICE_PROVIDER_TWILIO,
        "provider_call_id": provider_call.sid,
        "call_status": call_log.call_status,
    }


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


def build_gather_prompt_twiml(call_log_id: int, prompt_text: str | None = None) -> str:
    return build_gather_twiml(
        call_log_id,
        prompt_text or "Please say repeat summary, explain email number one, or no to end the call.",
    )


def build_slow_say(response: VoiceResponse | Gather, text: str) -> None:
    spoken_text = str(text or "").strip()
    if not spoken_text:
        return
    response.say(spoken_text, voice="alice", language="en-US")


def _ordered_summaries_for_call(db: Session, call_log: MailSummaryCallLog) -> list[EmailSummary]:
    summary_ids = _parse_delivered_summary_ids(call_log.delivered_summary_ids)
    if not summary_ids:
        return []

    summaries = (
        db.query(EmailSummary)
        .filter(
            EmailSummary.user_id == call_log.user_id,
            EmailSummary.id.in_(summary_ids),
        )
        .all()
    )
    summary_map = {summary.id: summary for summary in summaries}
    return [summary_map[summary_id] for summary_id in summary_ids if summary_id in summary_map]


def build_testable_call_script(db: Session, call_log: MailSummaryCallLog, max_items: int = MAX_TWIML_SUMMARY_ITEMS) -> str:
    summaries = _ordered_summaries_for_call(db, call_log)
    if not summaries:
        return "Hello. No emails received today."

    limited = summaries[:max_items]
    total_count = call_log.summary_count or len(summaries)
    parts = [f"Hello. You received {total_count} emails today."]
    if total_count > len(limited):
        parts.append(f"For this call, I will read the first {len(limited)} emails from today.")

    for index, summary in enumerate(limited, start=1):
        parts.append(
            " ".join(
                [
                    f"Email {index}.",
                    f"From {summary.sender or 'Unknown sender'}.",
                    f"Subject: {summary.subject or 'No subject'}.",
                    f"Summary: {summary.short_summary or 'Summary not available.'}",
                ]
            )
        )

    if total_count > len(limited):
        parts.append(
            f"You have more emails today, but I read the first {len(limited)} for this call. "
            "You can open the dashboard to view all summaries."
        )
    parts.append(
        "I have read today's email summaries. Is there any important mail you want me to explain in detail? "
        "You can say the email number, or say no to end the call."
    )
    return " ".join(parts)


def build_today_summary_twiml(db: Session, call_log: MailSummaryCallLog) -> str:
    response = VoiceResponse()
    build_slow_say(response, "This is your AI mail assistant with your prepared email summary call.")
    response.pause(length=1)
    script_text = build_testable_call_script(db, call_log)
    for chunk in _split_script(script_text):
        build_slow_say(response, chunk)
        response.pause(length=1)
    gather_twiml = Gather(
        input="speech dtmf",
        action=f"{_voice_base_url()}/voice/webhooks/twilio/speech?call_log_id={call_log.id}",
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
    build_slow_say(
        gather_twiml,
        "Is there any important mail you want me to explain in detail? You can say the email number, or say no to end the call.",
    )
    response.append(gather_twiml)
    build_slow_say(response, "I did not hear anything. I will end the call now. Have a good day.")
    response.hangup()
    return str(response)


def build_detail_email_twiml(call_log_id: int, detail_text: str) -> str:
    return build_gather_twiml(
        call_log_id,
        detail_text,
        "Do you want another email explained, or should I end the call?",
    )


def build_repeat_summary_twiml(db: Session, call_log: MailSummaryCallLog) -> str:
    return build_today_summary_twiml(db, call_log)


def build_end_call_twiml() -> str:
    response = VoiceResponse()
    build_slow_say(response, "Okay, ending the call. Have a good day.")
    response.hangup()
    return str(response)


def build_error_twiml(message: str = "Sorry, an application error occurred. Please try again later.") -> str:
    response = VoiceResponse()
    build_slow_say(response, message)
    response.hangup()
    return str(response)


def build_unknown_twiml(call_log_id: int) -> str:
    return build_gather_twiml(
        call_log_id,
        "Sorry, I did not understand. You can say repeat summary, explain email number one, or no to end the call.",
    )


def mail_call_twiml(db: Session, call_log_id: int) -> str:
    call_log = (
        db.query(MailSummaryCallLog)
        .filter(MailSummaryCallLog.id == call_log_id, MailSummaryCallLog.call_type == "mail_summary")
        .first()
    )
    if call_log is None or not call_log.script_text:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call script not found")
    if call_log.call_status not in {"prepared", "queued", "initiated", "ringing", "in_progress"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Call is not available for playback")
    return build_today_summary_twiml(db, call_log)


def _split_script(script_text: str, max_chunk_size: int = 900) -> list[str]:
    normalized = " ".join(script_text.split())
    if len(normalized) <= max_chunk_size:
        return [normalized]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for sentence in normalized.split(". "):
        sentence = sentence.strip()
        if not sentence:
            continue
        segment = sentence if sentence.endswith(".") else f"{sentence}."
        if current and current_len + len(segment) + 1 > max_chunk_size:
            chunks.append(" ".join(current))
            current = [segment]
            current_len = len(segment)
        else:
            current.append(segment)
            current_len += len(segment) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks


def process_twilio_status_callback(
    db: Session,
    provider_call_id: str,
    call_status: str,
    call_duration: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    call_log = _get_mail_call_by_provider_call_id(db, provider_call_id)

    now = datetime.now(timezone.utc)
    call_log.provider_status = call_status
    call_log.updated_at = now

    if call_status == "initiated":
        call_log.call_status = "initiated"
        call_log.call_started_at = call_log.call_started_at or now
    elif call_status == "ringing":
        call_log.call_status = "ringing"
        call_log.call_started_at = call_log.call_started_at or now
    elif call_status in {"in-progress", "answered"}:
        call_log.call_status = "in_progress"
        call_log.call_started_at = call_log.call_started_at or now
    elif call_status == TWILIO_COMPLETED_STATE:
        call_log.call_status = "completed"
        call_log.delivery_status = "delivered"
        call_log.call_completed_at = now
        if call_duration and call_duration.isdigit():
            call_log.call_duration_seconds = int(call_duration)
        db.add(call_log)
        db.commit()
        if call_log.user_id:
            user = db.query(User).filter(User.id == call_log.user_id).first()
            if user is not None:
                mark_mail_call_delivered(db, user, call_log.id)
        return
    elif call_status in TWILIO_TERMINAL_FAILURE_STATES:
        call_log.call_status = call_status.replace("-", "_")
        call_log.delivery_status = "failed"
        call_log.call_completed_at = now
        call_log.failure_reason = error_message or error_code or call_status
        call_log.provider_error_message = error_message or error_code
    else:
        call_log.call_status = call_status.replace("-", "_")

    if error_message or error_code:
        call_log.provider_error_message = error_message or error_code
        if call_log.delivery_status != "delivered":
            call_log.failure_reason = error_message or error_code

    db.add(call_log)
    db.commit()


def _next_interaction_order(db: Session, call_log_id: int) -> int:
    last = (
        db.query(VoiceCallInteraction)
        .filter(VoiceCallInteraction.mail_call_log_id == call_log_id)
        .order_by(VoiceCallInteraction.interaction_order.desc())
        .first()
    )
    return 1 if last is None else last.interaction_order + 1


def _interaction_count_for_intent(db: Session, call_log_id: int, intent: str) -> int:
    return db.query(VoiceCallInteraction).filter(
        VoiceCallInteraction.mail_call_log_id == call_log_id,
        VoiceCallInteraction.detected_intent == intent,
    ).count()


def _summary_for_reference(db: Session, call_log: MailSummaryCallLog, email_reference: int | None) -> EmailSummary:
    if not email_reference or email_reference < 1:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email number not found")

    summary_ids = _parse_delivered_summary_ids(call_log.delivered_summary_ids)
    if email_reference > len(summary_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email number not found")

    summary_id = summary_ids[email_reference - 1]
    summary = db.query(EmailSummary).filter(EmailSummary.id == summary_id, EmailSummary.user_id == call_log.user_id).first()
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email number not found")
    return summary


def _last_explained_email_reference(db: Session, call_log: MailSummaryCallLog) -> int | None:
    interaction = (
        db.query(VoiceCallInteraction)
        .filter(
            VoiceCallInteraction.mail_call_log_id == call_log.id,
            VoiceCallInteraction.detected_intent == INTENT_DETAIL_EMAIL,
            VoiceCallInteraction.email_reference.is_not(None),
        )
        .order_by(VoiceCallInteraction.interaction_order.desc(), VoiceCallInteraction.id.desc())
        .first()
    )
    return interaction.email_reference if interaction else None


def _last_explained_email_for_call(db: Session, call_log: MailSummaryCallLog) -> EmailSummary | None:
    resolved = get_last_explained_email_for_call(db, call_log)
    if not resolved:
        return None
    summary = resolved.get("email_summary")
    return summary if isinstance(summary, EmailSummary) else None


def _current_call_summary_count(call_log: MailSummaryCallLog) -> int:
    return len(_parse_delivered_summary_ids(call_log.delivered_summary_ids))


def _parse_delivered_summary_ids(payload: str | None) -> list[int]:
    if not payload:
        return []
    import json

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [int(item) for item in data]
    return []


def _record_interaction(
    db: Session,
    call_log: MailSummaryCallLog,
    transcript: str | None,
    detected_intent: str,
    email_reference: int | None,
    confidence: str | None,
    system_response_text: str,
) -> None:
    interaction = VoiceCallInteraction(
        user_id=call_log.user_id,
        mail_call_log_id=call_log.id,
        provider_call_id=call_log.provider_call_id,
        interaction_order=_next_interaction_order(db, call_log.id),
        user_transcript=transcript,
        detected_intent=detected_intent,
        email_reference=email_reference,
        confidence=confidence,
        system_response_text=system_response_text,
    )
    db.add(interaction)
    db.commit()


def _reply_prompt_twiml(call_log_id: int, prompt: str) -> str:
    return build_gather_twiml(call_log_id, prompt)


def process_twilio_speech_webhook(
    db: Session,
    provider_call_id: str | None,
    call_log_id: int | None,
    speech_result: str | None,
    confidence: str | None,
    digits: str | None = None,
) -> str:
    if provider_call_id:
        call_log = _get_mail_call_by_provider_call_id(db, provider_call_id)
    elif call_log_id:
        call_log = (
            db.query(MailSummaryCallLog)
            .filter(MailSummaryCallLog.id == call_log_id, MailSummaryCallLog.call_type == "mail_summary")
            .first()
        )
        if call_log is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid call_log_id")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid provider_call_id")

    transcript = (speech_result or "").strip()
    logger.info(
        "Twilio speech received %s",
        {
            "call_log_id": call_log.id,
            "provider_call_id": provider_call_id or call_log.provider_call_id,
            "speech_result": transcript,
            "confidence": confidence,
            "detected_intent": None,
            "active_reply_session": False,
            "active_reminder_session": False,
        },
    )

    active_reply = get_active_reply_session(db, call_log.user, call_log)
    if active_reply is not None:
        parsed = parse_voice_intent(transcript)
        if digits and not parsed.digits:
            parsed.digits = digits
        if active_reply.status == "awaiting_body":
            if parsed.intent in {INTENT_CANCEL_REPLY, INTENT_END_CALL}:
                cancel_reply(db, active_reply, "user cancelled during reply body capture")
                _record_interaction(db, call_log, transcript, INTENT_CANCEL_REPLY, active_reply.target_email_reference, confidence, "Okay. I cancelled the reply.")
                return build_gather_prompt_twiml(call_log.id, "Okay. I cancelled the reply.")
            body = parsed.reply_body or transcript.strip()
            if not body:
                system_response = "What would you like me to say?"
                _record_interaction(db, call_log, transcript, INTENT_CAPTURE_REPLY_BODY, active_reply.target_email_reference, confidence, system_response)
                return build_gather_prompt_twiml(call_log.id, system_response)
            update_reply_body(db, active_reply, body)
            system_response = f"You want to reply: {body}. Should I send this reply?"
            _record_interaction(db, call_log, transcript, INTENT_CAPTURE_REPLY_BODY, active_reply.target_email_reference, confidence, system_response)
            return build_gather_prompt_twiml(call_log.id, system_response)
        if active_reply.status == "awaiting_confirmation":
            if parsed.intent == INTENT_CONFIRM_SEND_REPLY:
                try:
                    send_reply(db, call_log.user, active_reply)
                except HTTPException as exc:
                    _record_interaction(db, call_log, transcript, INTENT_CONFIRM_SEND_REPLY, active_reply.target_email_reference, confidence, str(exc.detail))
                    return build_end_call_twiml()
                _record_interaction(db, call_log, transcript, INTENT_CONFIRM_SEND_REPLY, active_reply.target_email_reference, confidence, "Done. I sent the reply.")
                return build_end_call_twiml()
            if parsed.intent in {INTENT_CANCEL_REPLY, INTENT_END_CALL}:
                cancel_reply(db, active_reply, "user cancelled during confirmation")
                _record_interaction(db, call_log, transcript, INTENT_CANCEL_REPLY, active_reply.target_email_reference, confidence, "Okay. I cancelled the reply.")
                return build_end_call_twiml()
            if parsed.intent == INTENT_EDIT_REPLY:
                active_reply.status = "awaiting_body"
                active_reply.updated_at = datetime.now(timezone.utc)
                db.add(active_reply)
                db.commit()
                system_response = "Please say the full reply message again."
                _record_interaction(db, call_log, transcript, INTENT_EDIT_REPLY, active_reply.target_email_reference, confidence, system_response)
                return build_gather_prompt_twiml(call_log.id, system_response)
            system_response = "Should I send this reply? Please say yes to send or no to cancel."
            _record_interaction(db, call_log, transcript, INTENT_UNKNOWN, active_reply.target_email_reference, confidence, system_response)
            return build_gather_prompt_twiml(call_log.id, system_response)

    active_reminder = get_active_reminder_session(db, call_log.user, call_log)
    if active_reminder is not None:
        parsed = parse_voice_intent(transcript)
        if digits and not parsed.digits:
            parsed.digits = digits
        if active_reminder.status == "awaiting_details":
            reminder_dt = parse_reminder_datetime(transcript, call_log.user.timezone)
            normalized = (transcript or "").strip().lower()
            if digits == "2" or parsed.intent in {INTENT_CANCEL_REMINDER_CREATE, INTENT_END_CALL} or normalized in {"no", "cancel", "no cancel", "cancel reminder", "stop", "don't save", "dont save", "do not save"}:
                process_reminder_session_webhook(db, call_log, active_reminder, transcript, confidence, parsed)
                _record_interaction(db, call_log, transcript, INTENT_CANCEL_REMINDER_CREATE, active_reminder.target_email_reference, confidence, "Okay, I cancelled the reminder creation.")
                return build_reminder_end_call_twiml()
            if reminder_dt is None:
                system_response = "What date and time should I set the reminder for? You can say tomorrow at 3 pm, or Monday at 10 am."
                _record_interaction(db, call_log, transcript, INTENT_CAPTURE_REMINDER_DATETIME, active_reminder.target_email_reference, confidence, system_response)
                return build_reminder_details_prompt(call_log.id)
            update_reminder_details(db, active_reminder, reminder_dt, active_reminder.reminder_timezone or call_log.user.timezone or "UTC")
            confirmation_text = (
                f"I will create a reminder titled {active_reminder.reminder_title or 'Email follow-up reminder'} "
                f"for {reminder_dt.astimezone(timezone.utc).strftime('%A %B %d at %I:%M %p UTC')}. "
                "Please say yes to create the reminder, or no to cancel."
            )
            _record_interaction(db, call_log, transcript, INTENT_CAPTURE_REMINDER_DATETIME, active_reminder.target_email_reference, confidence, confirmation_text)
            return build_reminder_confirmation_twiml(call_log.id, confirmation_text)
        if active_reminder.status == "awaiting_confirmation":
            normalized = (transcript or "").strip().lower()
            if digits == "1" or parsed.intent in {INTENT_CONFIRM_CREATE_REMINDER} or normalized in {"yes", "yeah", "yep", "ok", "okay", "create it", "create", "yes create it", "yes save it", "save it", "save", "save this", "okay save it", "ok save it", "yeah save it", "yes please", "do it", "confirm"} or normalized.startswith("yes "):
                try:
                    process_reminder_session_webhook(db, call_log, active_reminder, transcript, confidence, parsed)
                except Exception as exc:
                    _record_interaction(db, call_log, transcript, INTENT_UNKNOWN, active_reminder.target_email_reference, confidence, f"Sorry, I could not create the reminder. {exc}")
                    return build_end_call_twiml()
                _record_interaction(db, call_log, transcript, INTENT_CONFIRM_CREATE_REMINDER, active_reminder.target_email_reference, confidence, "Your reminder has been created.")
                return build_reminder_created_twiml()
            if digits == "2" or parsed.intent in {INTENT_CANCEL_REMINDER_CREATE, INTENT_END_CALL} or normalized in {"no", "cancel", "no cancel", "cancel reminder", "stop", "don't save", "dont save", "do not save"}:
                process_reminder_session_webhook(db, call_log, active_reminder, transcript, confidence, parsed)
                _record_interaction(db, call_log, transcript, INTENT_CANCEL_REMINDER_CREATE, active_reminder.target_email_reference, confidence, "Okay, I cancelled the reminder creation.")
                return build_reminder_cancellation_twiml()
            confirmation_text = (
                f"I will create a reminder titled {active_reminder.reminder_title or 'Email follow-up reminder'} "
                f"for {active_reminder.reminder_at.astimezone(timezone.utc).strftime('%A %B %d at %I:%M %p UTC') if active_reminder.reminder_at else 'the requested time'}. "
                "Say yes save it, or press 1 to save. Say no cancel, or press 2 to cancel."
            )
            _record_interaction(db, call_log, transcript, INTENT_UNKNOWN, active_reminder.target_email_reference, confidence, confirmation_text)
            return build_reminder_confirmation_twiml(call_log.id, confirmation_text)

    parsed_intent = parse_voice_intent(transcript)
    if digits and not parsed_intent.digits:
        parsed_intent.digits = digits
    intent = parsed_intent.intent
    email_reference = parsed_intent.email_reference
    if confidence is not None and confidence.strip():
        try:
            if float(confidence) < 0.2:
                intent = INTENT_UNKNOWN
        except ValueError:
            intent = INTENT_UNKNOWN

    last_explained_reference = _last_explained_email_reference(db, call_log)
    smart_resolution = resolve_smart_voice_intent(
        transcript,
        parsed_intent,
        call_log.user.timezone,
        last_explained_email_reference=last_explained_reference,
    )
    if smart_resolution.needs_clarification and (intent == INTENT_UNKNOWN or smart_resolution.intent != INTENT_UNKNOWN):
        clarification = smart_resolution.clarification_question or "I can help with your emails during this call."
        _record_interaction(
            db,
            call_log,
            transcript,
            smart_resolution.intent if smart_resolution.intent != INTENT_UNKNOWN else INTENT_UNKNOWN,
            smart_resolution.email_reference,
            confidence,
            clarification,
        )
        return build_gather_prompt_twiml(call_log.id, clarification)

    if smart_resolution.intent == INTENT_NEXT_EMAIL:
        intent = INTENT_DETAIL_EMAIL
        email_reference = (last_explained_reference or 0) + 1
    elif smart_resolution.intent == INTENT_PREVIOUS_EMAIL:
        intent = INTENT_DETAIL_EMAIL
        email_reference = max(1, (last_explained_reference or 2) - 1)
    elif smart_resolution.intent != INTENT_UNKNOWN:
        intent = smart_resolution.intent
        if smart_resolution.email_reference is not None:
            email_reference = smart_resolution.email_reference
        if smart_resolution.reminder_datetime_iso:
            parsed_intent.reminder_datetime_iso = smart_resolution.reminder_datetime_iso

    repeat_count = _interaction_count_for_intent(db, call_log.id, INTENT_REPEAT_SUMMARY)
    detail_count = _interaction_count_for_intent(db, call_log.id, INTENT_DETAIL_EMAIL)
    unknown_count = _interaction_count_for_intent(db, call_log.id, INTENT_UNKNOWN)
    silence_count = db.query(VoiceCallInteraction).filter(
        VoiceCallInteraction.mail_call_log_id == call_log.id,
        VoiceCallInteraction.detected_intent == INTENT_UNKNOWN,
        VoiceCallInteraction.user_transcript.in_(["", None]),
    ).count()

    if intent == INTENT_REPEAT_SUMMARY:
        if repeat_count >= MAX_REPEAT_REQUESTS:
            system_response = "I have already repeated today's summaries once. I will end the call now. Have a good day."
            _record_interaction(db, call_log, transcript, INTENT_END_CALL, email_reference, confidence, system_response)
            return build_end_call_twiml()
        system_response = "Repeating today's summaries. Do you want any email explained in detail, or should I end the call?"
        _record_interaction(db, call_log, transcript, intent, email_reference, confidence, system_response)
        return build_repeat_summary_twiml(db, call_log)

    if intent == INTENT_DETAIL_EMAIL:
        if detail_count >= MAX_DETAIL_REQUESTS:
            system_response = "I have already explained two emails on this call. I will end the call now. Have a good day."
            _record_interaction(db, call_log, transcript, INTENT_END_CALL, email_reference, confidence, system_response)
            return build_end_call_twiml()
        resolved = resolve_email_reference_for_call(db, call_log.user, call_log, parsed_intent)
        lookup_status = resolved.get("status")
        if lookup_status == "invalid_reference":
            system_response = resolved.get("message") or "I only read five emails in this call. Please say a number between one and five, or say no to end the call."
            _record_interaction(db, call_log, transcript, INTENT_UNKNOWN, email_reference, confidence, system_response)
            return build_gather_prompt_twiml(call_log.id, system_response)
        if lookup_status == "multiple_matches":
            matches = resolved.get("matches") or []
            parts = ["I found multiple matching emails."]
            for match in matches[:3]:
                sender = match.get("sender") or "Unknown sender"
                subject = match.get("subject") or "No subject"
                parts.append(f"Email {match.get('email_reference')}. From {sender}. Subject: {subject}.")
            parts.append("Please say email number one, two, or three.")
            system_response = " ".join(parts)
            _record_interaction(db, call_log, transcript, INTENT_UNKNOWN, email_reference, confidence, system_response)
            return build_gather_prompt_twiml(call_log.id, system_response)
        if lookup_status == "no_match":
            system_response = resolved.get("message") or "I could not find a matching email from today's summaries. You can say email number one, repeat summary, or no to end the call."
            _record_interaction(db, call_log, transcript, INTENT_UNKNOWN, email_reference, confidence, system_response)
            return build_gather_prompt_twiml(call_log.id, system_response)

        summary = resolved.get("email_summary")
        matched_reference = resolved.get("email_reference") or email_reference
        detail_text = getattr(summary, "detailed_summary", None) or "No detailed summary is available for that email."
        system_response = (
            f"Email {matched_reference}. {detail_text} "
            "You can say: remind me about this email in two minutes. Or say: reply to this email. Or say: no to end the call."
        )
        _record_interaction(db, call_log, transcript, intent, matched_reference, confidence, system_response)
        return build_detail_email_twiml(call_log.id, detail_text)

    if intent == INTENT_END_CALL:
        system_response = "Okay, ending the call. Have a good day."
        _record_interaction(db, call_log, transcript, intent, email_reference, confidence, system_response)
        return build_end_call_twiml()

    if intent == INTENT_HELP:
        system_response = "You can say repeat summary, explain email number one, reply to this email, or no to end the call."
        _record_interaction(db, call_log, transcript, intent, email_reference, confidence, system_response)
        return build_gather_prompt_twiml(call_log.id, system_response)

    if intent == INTENT_TODAY_SUMMARY:
        system_response = "Repeating today's summaries. Do you want any email explained in detail, or should I end the call?"
        _record_interaction(db, call_log, transcript, intent, email_reference, confidence, system_response)
        return build_repeat_summary_twiml(db, call_log)

    if intent == INTENT_IMPORTANT_CHECK:
        system_response = "I can help you review any email in detail. Please say the email number you want me to explain."
        _record_interaction(db, call_log, transcript, intent, email_reference, confidence, system_response)
        return build_gather_prompt_twiml(call_log.id, system_response)

    if intent == INTENT_START_EMAIL_REPLY:
        target_summary = None
        target_ref = parsed_intent.target_email_reference or parsed_intent.email_reference
        if target_ref is not None:
            try:
                target_summary = _summary_for_reference(db, call_log, target_ref)
            except HTTPException:
                target_summary = None
        elif parsed_intent.target_lookup_type or parsed_intent.target_lookup_query:
            target_intent = ParsedVoiceIntent(
                intent=INTENT_DETAIL_EMAIL,
                email_reference=None,
                confidence=parsed_intent.confidence,
                normalized_transcript=parsed_intent.normalized_transcript,
                reason=parsed_intent.reason,
                lookup_query=parsed_intent.target_lookup_query,
                lookup_type=parsed_intent.target_lookup_type or LOOKUP_UNKNOWN,
                sender_query=parsed_intent.target_lookup_query if parsed_intent.target_lookup_type == "sender" else None,
                subject_query=parsed_intent.target_lookup_query if parsed_intent.target_lookup_type == "subject" else None,
                keyword_query=parsed_intent.target_lookup_query if parsed_intent.target_lookup_type == "keyword" else None,
                ordinal_reference=parsed_intent.target_lookup_query if parsed_intent.target_lookup_type in {LOOKUP_LATEST, LOOKUP_FIRST, LOOKUP_LAST} else None,
            )
            resolved = resolve_email_reference_for_call(db, call_log.user, call_log, target_intent)
            if resolved.get("status") == "matched":
                target_summary = resolved.get("email_summary")
                target_ref = resolved.get("email_reference")
            elif resolved.get("status") == "multiple_matches":
                system_response = resolved.get("message") or "I found multiple matching emails. Please say the email number you want to reply to."
                _record_interaction(db, call_log, transcript, INTENT_START_EMAIL_REPLY, None, confidence, system_response)
                return build_gather_prompt_twiml(call_log.id, system_response)
            else:
                system_response = "I could not find a matching email from today's summaries. You can say email number one, repeat summary, or no to end the call."
                _record_interaction(db, call_log, transcript, INTENT_START_EMAIL_REPLY, None, confidence, system_response)
                return build_gather_prompt_twiml(call_log.id, system_response)
        else:
            last_ref = _last_explained_email_reference(db, call_log)
            if last_ref is not None:
                target_summary = _summary_for_reference(db, call_log, last_ref)
                target_ref = last_ref
        if target_summary is None:
            system_response = "Which email should I reply to? Please say email number one, or describe the email."
            _record_interaction(db, call_log, transcript, INTENT_START_EMAIL_REPLY, None, confidence, system_response)
            return build_gather_prompt_twiml(call_log.id, system_response)
        if parsed_intent.reply_body:
            session = start_reply_session(db, call_log.user, call_log, target_summary, reply_body=parsed_intent.reply_body, target_email_reference=target_ref)
            system_response = f"You want to reply: {parsed_intent.reply_body}. Should I send this reply?"
            _record_interaction(db, call_log, transcript, INTENT_START_EMAIL_REPLY, target_ref, confidence, system_response)
            return build_gather_prompt_twiml(call_log.id, system_response)
        start_reply_session(db, call_log.user, call_log, target_summary, target_email_reference=target_ref)
        system_response = "What would you like me to say?"
        _record_interaction(db, call_log, transcript, INTENT_START_EMAIL_REPLY, target_ref, confidence, system_response)
        return build_gather_prompt_twiml(call_log.id, system_response)

    if intent in {INTENT_START_REMINDER_CREATE, INTENT_CREATE_RECURRING_REMINDER}:
        if smart_resolution.intent == INTENT_CREATE_RECURRING_REMINDER:
            session = start_reminder_session(
                db,
                call_log.user,
                call_log,
                None,
                target_email_reference=parsed_intent.target_email_reference or parsed_intent.email_reference,
                reminder_text=parsed_intent.reminder_text or transcript,
                repeat_type=smart_resolution.repeat_type,
                interval_value=smart_resolution.interval_value,
                interval_unit=smart_resolution.interval_unit,
                days_of_week=smart_resolution.days_of_week,
                day_of_month=smart_resolution.day_of_month,
                time_of_day=smart_resolution.time_of_day,
            )
            if not _recurring_payload_is_ready(smart_resolution):
                system_response = (
                    "What repeat schedule should I use? You can say every day at 8 pm, every Monday at 9 am, "
                    "or every 2 hours."
                )
                _record_interaction(db, call_log, transcript, INTENT_CREATE_RECURRING_REMINDER, None, confidence, system_response)
                return build_gather_prompt_twiml(call_log.id, system_response)
            session.status = "awaiting_confirmation"
            session.updated_at = datetime.now(timezone.utc)
            db.add(session)
            db.commit()
            db.refresh(session)
            confirmation_text = _recurring_confirmation_text(session)
            _record_interaction(db, call_log, transcript, INTENT_CREATE_RECURRING_REMINDER, session.target_email_reference, confidence, confirmation_text)
            return build_reminder_confirmation_twiml(call_log.id, confirmation_text)

        target_summary = None
        target_ref = parsed_intent.target_email_reference or parsed_intent.email_reference
        if target_ref is not None:
            try:
                target_summary = _summary_for_reference(db, call_log, target_ref)
            except HTTPException:
                target_summary = None
        elif any(marker in (transcript or "").lower() for marker in ("this email", "this mail", "this one")):
            last_resolved = get_last_explained_email_for_call(db, call_log)
            if last_resolved and last_resolved.get("email_summary") is not None:
                target_summary = last_resolved.get("email_summary")
                target_ref = last_resolved.get("email_reference")
        elif parsed_intent.target_lookup_type or parsed_intent.target_lookup_query:
            target_intent = ParsedVoiceIntent(
                intent=INTENT_DETAIL_EMAIL,
                email_reference=None,
                confidence=parsed_intent.confidence,
                normalized_transcript=parsed_intent.normalized_transcript,
                reason=parsed_intent.reason,
                lookup_query=parsed_intent.target_lookup_query,
                lookup_type=parsed_intent.target_lookup_type or LOOKUP_UNKNOWN,
                sender_query=parsed_intent.target_lookup_query if parsed_intent.target_lookup_type == "sender" else None,
                subject_query=parsed_intent.target_lookup_query if parsed_intent.target_lookup_type == "subject" else None,
                keyword_query=parsed_intent.target_lookup_query if parsed_intent.target_lookup_type == "keyword" else None,
                ordinal_reference=parsed_intent.target_lookup_query if parsed_intent.target_lookup_type in {LOOKUP_LATEST, LOOKUP_FIRST, LOOKUP_LAST} else None,
            )
            resolved = resolve_email_reference_for_call(db, call_log.user, call_log, target_intent)
            if resolved.get("status") == "matched":
                target_summary = resolved.get("email_summary")
                target_ref = resolved.get("email_reference")
            elif resolved.get("status") == "multiple_matches":
                system_response = resolved.get("message") or "I found multiple matching emails. Please say the email number you want a reminder for."
                _record_interaction(db, call_log, transcript, INTENT_START_REMINDER_CREATE, None, confidence, system_response)
                return build_gather_prompt_twiml(call_log.id, system_response)
            else:
                system_response = "Which email should I create the reminder for? Please say email number one, or describe the email."
                _record_interaction(db, call_log, transcript, INTENT_START_REMINDER_CREATE, None, confidence, system_response)
                return build_gather_prompt_twiml(call_log.id, system_response)

        reminder_dt = parse_reminder_datetime(transcript, call_log.user.timezone)
        if reminder_dt is None and parsed_intent.reminder_datetime_iso:
            try:
                reminder_dt = datetime.fromisoformat(parsed_intent.reminder_datetime_iso)
            except ValueError:
                reminder_dt = None
        if target_summary is None and any(marker in (transcript or "").lower() for marker in ("this email", "this mail", "this one")):
            system_response = "Which email should I create the reminder for? Please say email number one, or describe the email."
            _record_interaction(db, call_log, transcript, INTENT_START_REMINDER_CREATE, None, confidence, system_response)
            return build_gather_prompt_twiml(call_log.id, system_response)
        session = start_reminder_session(
            db,
            call_log.user,
            call_log,
            target_summary,
            target_email_reference=target_ref,
            reminder_datetime=reminder_dt,
            reminder_text=parsed_intent.reminder_text,
        )
        if reminder_dt is not None:
            confirmation_text = (
                f"I will create a reminder titled {session.reminder_title or 'Email follow-up reminder'} "
                f"for {reminder_dt.astimezone(timezone.utc).strftime('%A %B %d at %I:%M %p UTC')}. "
                "Say yes save it, or press 1 to save. Say no cancel, or press 2 to cancel."
            )
            _record_interaction(db, call_log, transcript, INTENT_START_REMINDER_CREATE, target_ref, confidence, confirmation_text)
            return build_reminder_confirmation_twiml(call_log.id, confirmation_text)
        system_response = "What date and time should I set the reminder for? You can say tomorrow at 3 pm, or Monday at 10 am."
        _record_interaction(db, call_log, transcript, INTENT_START_REMINDER_CREATE, target_ref, confidence, system_response)
        return build_reminder_details_prompt(call_log.id)

    if not transcript:
        if silence_count >= MAX_SILENCE_REQUESTS:
            system_response = "I did not hear anything. I will end the call now. Have a good day."
            _record_interaction(db, call_log, transcript, INTENT_END_CALL, email_reference, confidence, system_response)
            return build_end_call_twiml()
        system_response = "I did not hear anything. Please say repeat summary, explain email number one, or no to end the call."
        _record_interaction(db, call_log, transcript, INTENT_UNKNOWN, email_reference, confidence, system_response)
        return build_gather_prompt_twiml(call_log.id, system_response)

    if unknown_count >= MAX_UNKNOWN_REQUESTS - 1:
        system_response = "Sorry, I still did not understand. I will end the call now. Have a good day."
        _record_interaction(db, call_log, transcript, INTENT_END_CALL, email_reference, confidence, system_response)
        return build_end_call_twiml()

    if smart_resolution.needs_clarification:
        system_response = smart_resolution.clarification_question or "I can help with your emails during this call."
    else:
        system_response = "Sorry, I did not understand. You can say repeat summary, explain email one, remind me about this email, reply to this email, or no to end the call."
    _record_interaction(db, call_log, transcript, INTENT_UNKNOWN, email_reference, confidence, system_response)
    return build_unknown_twiml(call_log.id)


def list_voice_call_interactions(db: Session, user: User, call_log_id: int) -> list[VoiceCallInteraction]:
    call_log = get_mail_call_for_user(db, user, call_log_id)
    return (
        db.query(VoiceCallInteraction)
        .filter(VoiceCallInteraction.mail_call_log_id == call_log.id, VoiceCallInteraction.user_id == user.id)
        .order_by(VoiceCallInteraction.interaction_order.asc(), VoiceCallInteraction.id.asc())
        .all()
    )


def voice_interaction_to_item(interaction: VoiceCallInteraction) -> dict[str, object]:
    return {
        "id": interaction.id,
        "user_transcript": interaction.user_transcript,
        "detected_intent": interaction.detected_intent,
        "email_reference": interaction.email_reference,
        "confidence": interaction.confidence,
        "system_response_text": interaction.system_response_text,
        "interaction_order": interaction.interaction_order,
        "created_at": interaction.created_at,
    }
