from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

from app.config import settings
from app.models.reminder import Reminder
from app.models.user import User

logger = logging.getLogger(__name__)

REMINDER_PROVIDER_TWILIO = "twilio"


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
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Missing reminder provider configuration: {', '.join(missing)}")


def _twilio_client() -> Client:
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def _voice_base_url() -> str:
    return settings.public_backend_url.rstrip("/")


def build_reminder_twiml(reminder: Reminder) -> str:
    title = (reminder.title or "").strip().rstrip(".")
    notes = (reminder.notes or "").strip().rstrip(".")
    response = VoiceResponse()
    response.say("Hello. This is your reminder.", voice="alice", language="en-US")
    response.pause(length=1)
    response.say(f"Reminder: {title}.", voice="alice", language="en-US")
    if notes:
        response.pause(length=1)
        response.say(f"Notes: {notes}.", voice="alice", language="en-US")
    response.pause(length=1)
    response.say("Thank you. Goodbye.", voice="alice", language="en-US")
    response.hangup()
    return str(response)


def start_reminder_call(db: Session, reminder: Reminder, user: User) -> dict[str, str]:
    _require_twilio_config()
    to_phone = (reminder.phone_number or user.phone_number or "").strip()
    if not to_phone:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reminder requires a phone number")
    client = _twilio_client()
    twiml_url = f"{_voice_base_url()}/voice/reminders/{reminder.id}/twiml"
    status_callback = f"{_voice_base_url()}/voice/webhooks/twilio/reminder-status?reminder_id={reminder.id}"

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
        reminder.status = "failed"
        reminder.provider = REMINDER_PROVIDER_TWILIO
        reminder.last_error = "Twilio API failure"
        reminder.updated_at = datetime.now(timezone.utc)
        db.add(reminder)
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Twilio API failure") from exc

    reminder.provider = REMINDER_PROVIDER_TWILIO
    reminder.provider_call_id = provider_call.sid
    reminder.status = "calling"
    reminder.called_at = reminder.called_at or datetime.now(timezone.utc)
    reminder.last_error = None
    reminder.updated_at = datetime.now(timezone.utc)
    db.add(reminder)
    db.commit()
    return {"provider": REMINDER_PROVIDER_TWILIO, "provider_call_id": provider_call.sid, "status": reminder.status}
