import logging

from fastapi import APIRouter, Depends, Form, Response
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.reminder import Reminder
from app.schemas.mail_call import VoiceCallInteractionItem, VoiceCallStartResponse
from app.services.voice_call_service import (
    build_error_twiml,
    list_voice_call_interactions,
    mail_call_twiml,
    process_twilio_status_callback,
    process_twilio_speech_webhook,
    start_mail_summary_voice_call,
    voice_interaction_to_item,
)
from app.services.reminder_service import process_twilio_reminder_status_callback
from app.services.reminder_voice_service import build_reminder_twiml

router = APIRouter(prefix="/voice", tags=["voice"])
logger = logging.getLogger(__name__)


@router.post("/mail-calls/{call_log_id}/start", response_model=VoiceCallStartResponse)
def start_voice_call(call_log_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> VoiceCallStartResponse:
    return VoiceCallStartResponse(**start_mail_summary_voice_call(db, current_user, call_log_id))


@router.get("/mail-calls/{call_log_id}/twiml")
def get_mail_call_twiml(call_log_id: int, db: Session = Depends(get_db)) -> Response:
    try:
        twiml = mail_call_twiml(db, call_log_id)
    except Exception:
        logger.exception("Failed to build TwiML for mail call %s", call_log_id)
        twiml = build_error_twiml()
    return Response(content=twiml, media_type="application/xml")


@router.post("/webhooks/twilio/status")
def twilio_status_webhook(
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: str | None = Form(default=None),
    ErrorCode: str | None = Form(default=None),
    ErrorMessage: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    process_twilio_status_callback(
        db=db,
        provider_call_id=CallSid,
        call_status=CallStatus,
        call_duration=CallDuration,
        error_code=ErrorCode,
        error_message=ErrorMessage,
    )
    return {"status": "ok"}


@router.post("/webhooks/twilio/speech")
def twilio_speech_webhook(
    CallSid: str | None = Form(default=None),
    SpeechResult: str | None = Form(default=None),
    Confidence: str | None = Form(default=None),
    Digits: str | None = Form(default=None),
    call_log_id: int | None = None,
    db: Session = Depends(get_db),
) -> Response:
    try:
        twiml = process_twilio_speech_webhook(
            db=db,
            provider_call_id=CallSid,
            call_log_id=call_log_id,
            speech_result=SpeechResult,
            confidence=Confidence,
            digits=Digits,
        )
    except Exception:
        logger.exception("Failed to process Twilio speech webhook for call %s", CallSid or call_log_id)
        twiml = build_error_twiml("Sorry, I could not process that request. Ending the call now.")
    return Response(content=twiml, media_type="application/xml")


@router.get("/mail-calls/{call_log_id}/interactions", response_model=list[VoiceCallInteractionItem])
def get_voice_interactions(call_log_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[VoiceCallInteractionItem]:
    interactions = list_voice_call_interactions(db, current_user, call_log_id)
    return [VoiceCallInteractionItem(**voice_interaction_to_item(item)) for item in interactions]


def _reminder_twiml_response(reminder_id: int, db: Session) -> Response:
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if reminder is None:
        return Response(content=build_error_twiml("Sorry, I could not find that reminder."), media_type="application/xml")
    try:
        twiml = build_reminder_twiml(reminder)
    except Exception:
        logger.exception("Failed to build reminder TwiML for reminder %s", reminder_id)
        twiml = build_error_twiml("Sorry, I could not read your reminder right now.")
    return Response(content=twiml, media_type="application/xml")


@router.get("/reminders/{reminder_id}/twiml")
def get_reminder_twiml(reminder_id: int, db: Session = Depends(get_db)) -> Response:
    return _reminder_twiml_response(reminder_id, db)


@router.post("/reminders/{reminder_id}/twiml")
def post_reminder_twiml(reminder_id: int, db: Session = Depends(get_db)) -> Response:
    return _reminder_twiml_response(reminder_id, db)


@router.post("/webhooks/twilio/reminder-status")
def twilio_reminder_status_webhook(
    reminder_id: int,
    CallSid: str | None = Form(default=None),
    CallStatus: str = Form(...),
    CallDuration: str | None = Form(default=None),
    ErrorCode: str | None = Form(default=None),
    ErrorMessage: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    process_twilio_reminder_status_callback(
        db=db,
        reminder_id=reminder_id,
        call_sid=CallSid,
        call_status=CallStatus,
        call_duration=CallDuration,
        error_code=ErrorCode,
        error_message=ErrorMessage,
    )
    return {"status": "ok"}
