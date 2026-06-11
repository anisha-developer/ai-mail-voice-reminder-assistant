from datetime import datetime, timezone

from app.services.smart_voice_intent_service import (
    INTENT_NEXT_EMAIL,
    INTENT_PREVIOUS_EMAIL,
    INTENT_START_REMINDER_CREATE,
    resolve_smart_voice_intent,
)
from app.services.voice_intent_service import INTENT_DETAIL_EMAIL, INTENT_END_CALL, INTENT_UNKNOWN, parse_voice_intent
from app.services.voice_reminder_service import parse_reminder_datetime


def test_smart_voice_intent_handles_natural_language_detail_and_navigation() -> None:
    detail = resolve_smart_voice_intent("Can you explain the first one?", parse_voice_intent("Can you explain the first one?"), "Asia/Kolkata")
    assert detail.intent == INTENT_DETAIL_EMAIL
    assert detail.email_reference == 1

    next_email = resolve_smart_voice_intent("Skip this and go to the next email", parse_voice_intent("Skip this and go to the next email"), "Asia/Kolkata", last_explained_email_reference=1)
    assert next_email.intent == INTENT_NEXT_EMAIL

    previous_email = resolve_smart_voice_intent("Go back to the previous email", parse_voice_intent("Go back to the previous email"), "Asia/Kolkata", last_explained_email_reference=2)
    assert previous_email.intent == INTENT_PREVIOUS_EMAIL


def test_smart_voice_intent_helps_with_ambiguous_inputs() -> None:
    reminder = resolve_smart_voice_intent("Remind me about this tomorrow morning", parse_voice_intent("Remind me about this tomorrow morning"), "Asia/Kolkata", last_explained_email_reference=1)
    assert reminder.intent == INTENT_START_REMINDER_CREATE
    assert reminder.reminder_datetime_iso is not None or reminder.needs_clarification is False

    vague = resolve_smart_voice_intent("Tell me more about this", parse_voice_intent("Tell me more about this"), "Asia/Kolkata")
    assert vague.intent in {INTENT_DETAIL_EMAIL, INTENT_UNKNOWN}
    assert vague.needs_clarification is True
    assert vague.clarification_question


def test_reminder_time_parsing_handles_exact_and_vague_times() -> None:
    assert parse_reminder_datetime("in 2 minutes", "Asia/Kolkata") is not None
    assert parse_reminder_datetime("in 5 minutes", "Asia/Kolkata") is not None
    assert parse_reminder_datetime("after 10 minutes", "Asia/Kolkata") is not None
    assert parse_reminder_datetime("at 6 PM", "Asia/Kolkata") is not None
    assert parse_reminder_datetime("tomorrow morning", "Asia/Kolkata") is not None
    assert parse_reminder_datetime("tomorrow at 9 AM", "Asia/Kolkata") is not None
    assert parse_reminder_datetime("next Monday at 10", "Asia/Kolkata") is not None
    assert parse_reminder_datetime("tomorrow", "Asia/Kolkata") is None


def test_end_call_intent_is_still_supported() -> None:
    parsed = resolve_smart_voice_intent("end the call", parse_voice_intent("end the call"), "Asia/Kolkata")
    assert parsed.intent == INTENT_END_CALL
    assert parsed.confidence >= 0.9
