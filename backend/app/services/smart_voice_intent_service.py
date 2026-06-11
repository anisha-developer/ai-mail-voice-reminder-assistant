from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import re
from zoneinfo import ZoneInfo

from app.core.timezone import normalize_timezone_name

from app.services.voice_intent_service import (
    INTENT_DETAIL_EMAIL,
    INTENT_END_CALL,
    INTENT_CREATE_RECURRING_REMINDER,
    INTENT_REPEAT_SUMMARY,
    INTENT_START_EMAIL_REPLY,
    INTENT_START_REMINDER_CREATE,
    INTENT_UNKNOWN,
    LOOKUP_FIRST,
    LOOKUP_LAST,
    LOOKUP_LATEST,
    ParsedVoiceIntent,
    normalize_transcript,
    parse_voice_intent,
)

logger = logging.getLogger(__name__)

INTENT_NEXT_EMAIL = "NEXT_EMAIL"
INTENT_PREVIOUS_EMAIL = "PREVIOUS_EMAIL"
INTENT_SEARCH_EMAIL = "SEARCH_EMAIL"
INTENT_CREATE_GENERAL_REMINDER = "CREATE_GENERAL_REMINDER"

DEFAULT_TIME_MAP = {
    "morning": "09:00",
    "afternoon": "14:00",
    "evening": "18:00",
    "night": "20:00",
    "tonight": "20:00",
    "after lunch": "14:00",
}


@dataclass(slots=True)
class SmartVoiceResolution:
    intent: str
    email_reference: int | None
    confidence: float
    normalized_transcript: str
    needs_clarification: bool = False
    clarification_question: str | None = None
    reminder_datetime_text: str | None = None
    reminder_datetime_iso: str | None = None
    repeat_type: str | None = None
    interval_value: int | None = None
    interval_unit: str | None = None
    days_of_week: list[str] | None = None
    day_of_month: int | None = None
    time_of_day: str | None = None
    target_lookup_type: str | None = None
    target_lookup_query: str | None = None
    reply_body: str | None = None
    source: str = "rules"


def _has_time_words(text: str) -> bool:
    return bool(
        re.search(r"\b(?:\d{1,2}[:.]\d{2}(?:\s*(?:am|pm))?|\d{1,2}\s*(?:am|pm)|noon|midnight|morning|afternoon|evening|night|tonight|after lunch|in\s+\d+|after\s+\d+)\b", text)
    )


def _has_date_words(text: str) -> bool:
    return bool(re.search(r"\b(?:today|tomorrow|tonight|next\s+\w+|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", text))


def _parse_time_only_reference(normalized: str, timezone_name: str) -> tuple[datetime | None, bool]:
    local_zone = ZoneInfo(normalize_timezone_name(timezone_name, "UTC"))
    base_now = datetime.now(local_zone)
    if normalized in {"tomorrow"}:
        return None, True
    direct_time_match = re.fullmatch(r"(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)", normalized)
    if direct_time_match:
        hour = int(direct_time_match.group(1))
        minute = int(direct_time_match.group(2) or "00")
        period = direct_time_match.group(3)
        if period == "pm" and hour != 12:
            hour += 12
        if period == "am" and hour == 12:
            hour = 0
        candidate = base_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= base_now:
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc), False
    if _has_date_words(normalized) and not _has_time_words(normalized):
        return None, True

    if "tomorrow morning" in normalized:
        candidate = base_now + timedelta(days=1)
        return candidate.replace(hour=9, minute=0, second=0, microsecond=0).astimezone(timezone.utc), False
    if "tomorrow afternoon" in normalized:
        candidate = base_now + timedelta(days=1)
        return candidate.replace(hour=14, minute=0, second=0, microsecond=0).astimezone(timezone.utc), False
    if "tomorrow evening" in normalized:
        candidate = base_now + timedelta(days=1)
        return candidate.replace(hour=18, minute=0, second=0, microsecond=0).astimezone(timezone.utc), False
    if "tomorrow night" in normalized or "tomorrow tonight" in normalized:
        candidate = base_now + timedelta(days=1)
        return candidate.replace(hour=20, minute=0, second=0, microsecond=0).astimezone(timezone.utc), False
    if normalized in DEFAULT_TIME_MAP:
        hour, minute = map(int, DEFAULT_TIME_MAP[normalized].split(":"))
        candidate = base_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if candidate <= base_now and normalized in {"night", "tonight"}:
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc), False

    try:
        from dateparser.search import search_dates

        matches = search_dates(
            normalized,
            settings={
                "RETURN_AS_TIMEZONE_AWARE": True,
                "TIMEZONE": timezone_name or "UTC",
                "TO_TIMEZONE": "UTC",
                "RELATIVE_BASE": base_now,
            },
        )
        if matches:
            for _, candidate in reversed(matches):
                if candidate is not None:
                    return candidate.astimezone(timezone.utc), False
    except Exception:
        logger.exception("Failed smart parse for reminder text=%r", normalized)
    return None, False


def _extract_time_of_day(normalized: str) -> str | None:
    match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", normalized)
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(2) or "00")
    period = match.group(3)
    if period == "pm" and hour != 12:
        hour += 12
    if period == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _extract_month_day(normalized: str) -> int | None:
    match = re.search(r"\bon\s+(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)?\b", normalized)
    if not match:
        return None
    return int(match.group(1))


def _extract_repeat_pattern(normalized: str) -> dict[str, object] | None:
    if "every" not in normalized and "weekdays" not in normalized:
        return None
    if "every day" in normalized or "daily" in normalized:
        return {"repeat_type": "daily", "time_of_day": _extract_time_of_day(normalized)}
    if "weekdays" in normalized:
        return {"repeat_type": "weekdays", "time_of_day": _extract_time_of_day(normalized)}
    if "every month" in normalized or "monthly" in normalized or "each month" in normalized:
        return {
            "repeat_type": "monthly",
            "day_of_month": _extract_month_day(normalized),
            "time_of_day": _extract_time_of_day(normalized),
        }
    interval_match = re.search(r"\bevery\s+(\d+)\s+(minutes?|hours?|days?|weeks?|months?)\b", normalized)
    if interval_match:
        return {
            "repeat_type": "custom_interval",
            "interval_value": int(interval_match.group(1)),
            "interval_unit": interval_match.group(2).rstrip("s"),
        }
    weekday_hits = [day for day in {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"} if day in normalized]
    if weekday_hits:
        repeat_type = "weekly" if "every" in normalized else "custom_days"
        return {
            "repeat_type": repeat_type,
            "days_of_week": weekday_hits,
            "time_of_day": _extract_time_of_day(normalized),
        }
    return None


def _clarify_unknown(normalized: str) -> tuple[str, str]:
    if "remind" in normalized:
        return INTENT_START_REMINDER_CREATE, "I can create that reminder. What time should I remind you?"
    if any(marker in normalized for marker in ("explain", "tell me more", "what about", "more about")):
        return INTENT_DETAIL_EMAIL, "Which email do you mean? You can say email one, email two, or mention the sender or subject."
    if "reply" in normalized:
        return INTENT_START_EMAIL_REPLY, "Which email should I reply to? You can say email one, email two, or mention the sender or subject."
    return INTENT_UNKNOWN, "I can help with your emails during this call. You can ask me to explain an email, create a reminder, reply to an email, repeat the summary, or end the call."


def resolve_smart_voice_intent(
    transcript: str | None,
    parsed_intent: ParsedVoiceIntent | None,
    timezone_name: str | None = None,
    last_explained_email_reference: int | None = None,
) -> SmartVoiceResolution:
    normalized = normalize_transcript(transcript)
    parsed = parsed_intent or parse_voice_intent(transcript)
    if parsed.intent != INTENT_UNKNOWN and parsed.confidence >= 0.6:
        recurring = _extract_repeat_pattern(normalized)
        if recurring and parsed.intent == INTENT_START_REMINDER_CREATE:
            return SmartVoiceResolution(
                intent=INTENT_CREATE_RECURRING_REMINDER,
                email_reference=None,
                confidence=parsed.confidence,
                normalized_transcript=parsed.normalized_transcript,
                repeat_type=recurring.get("repeat_type"),
                interval_value=recurring.get("interval_value"),
                interval_unit=recurring.get("interval_unit"),
                days_of_week=recurring.get("days_of_week"),
                day_of_month=recurring.get("day_of_month"),
                time_of_day=recurring.get("time_of_day"),
                source="rules",
            )
        reminder_iso, needs_time_clarification = _parse_time_only_reference(normalized, timezone_name or "UTC")
        clarification = None
        intent = parsed.intent
        email_reference = parsed.email_reference
        if intent == INTENT_DETAIL_EMAIL and email_reference is None:
            if parsed.ordinal_reference in {LOOKUP_FIRST, "first"} or "first" in normalized or re.search(r"\bone\b", normalized):
                email_reference = 1
            elif parsed.ordinal_reference in {LOOKUP_LAST, LOOKUP_LATEST, "last", "latest"}:
                email_reference = None
            elif "second" in normalized or re.search(r"\btwo\b", normalized):
                email_reference = 2
            elif "third" in normalized or re.search(r"\bthree\b", normalized):
                email_reference = 3
        if intent == INTENT_START_REMINDER_CREATE and not parsed.reminder_datetime_iso:
            if reminder_iso is not None:
                parsed.reminder_datetime_iso = reminder_iso.isoformat()
            elif needs_time_clarification:
                clarification = "What time should I set the reminder for?"
        return SmartVoiceResolution(
            intent=intent,
            email_reference=email_reference,
            confidence=parsed.confidence,
            normalized_transcript=parsed.normalized_transcript,
            needs_clarification=bool(clarification),
            clarification_question=clarification,
            reminder_datetime_text=parsed.reminder_datetime_text,
            reminder_datetime_iso=parsed.reminder_datetime_iso,
            target_lookup_type=parsed.target_lookup_type,
            target_lookup_query=parsed.target_lookup_query,
            reply_body=parsed.reply_body,
            source="rules",
        )

    if not normalized:
        return SmartVoiceResolution(
            intent=INTENT_UNKNOWN,
            email_reference=None,
            confidence=0.2,
            normalized_transcript=normalized,
            needs_clarification=True,
            clarification_question="I did not hear anything. Please say repeat summary, explain email one, remind me about this email, or end the call.",
            source="rules",
        )

    if any(marker in normalized for marker in ("repeat", "say again", "read again", "repeat summary")):
        return SmartVoiceResolution(INTENT_REPEAT_SUMMARY, None, 0.92, normalized, source="rules")

    if any(marker in normalized for marker in ("next email", "next one", "go to the next", "skip this and go to the next")):
        return SmartVoiceResolution(INTENT_NEXT_EMAIL, None, 0.86, normalized, source="rules")

    if any(marker in normalized for marker in ("previous email", "go back", "previous one", "go to the previous")):
        return SmartVoiceResolution(INTENT_PREVIOUS_EMAIL, None, 0.86, normalized, source="rules")

    if any(marker in normalized for marker in ("explain", "tell me more", "what about", "more about", "read", "describe")):
        email_reference = parsed.email_reference
        if email_reference is None and last_explained_email_reference is not None:
            if "this" in normalized or "that" in normalized or "it" in normalized:
                email_reference = last_explained_email_reference
        if email_reference is None and any(word in normalized for word in ("first", "one")):
            email_reference = 1
        if email_reference is None and any(word in normalized for word in ("second", "two")):
            email_reference = 2
        if email_reference is None and any(word in normalized for word in ("third", "three")):
            email_reference = 3
        if email_reference is None:
            intent, question = _clarify_unknown(normalized)
            return SmartVoiceResolution(
                intent=intent,
                email_reference=None,
                confidence=0.3,
                normalized_transcript=normalized,
                needs_clarification=True,
                clarification_question=question,
                source="rules",
            )
        return SmartVoiceResolution(INTENT_DETAIL_EMAIL, email_reference, 0.88, normalized, source="rules")

    if "reply" in normalized:
        return SmartVoiceResolution(INTENT_START_EMAIL_REPLY, None, 0.84, normalized, source="rules")

    if "remind" in normalized:
        recurring = _extract_repeat_pattern(normalized)
        if recurring:
            return SmartVoiceResolution(
                intent=INTENT_CREATE_RECURRING_REMINDER,
                email_reference=None,
                confidence=0.9,
                normalized_transcript=normalized,
                repeat_type=recurring.get("repeat_type"),
                interval_value=recurring.get("interval_value"),
                interval_unit=recurring.get("interval_unit"),
                days_of_week=recurring.get("days_of_week"),
                day_of_month=recurring.get("day_of_month"),
                time_of_day=recurring.get("time_of_day"),
                source="rules",
            )
        reminder_iso, needs_time_clarification = _parse_time_only_reference(normalized, timezone_name or "UTC")
        if "this" in normalized and last_explained_email_reference is None:
            return SmartVoiceResolution(
                intent=INTENT_START_REMINDER_CREATE,
                email_reference=None,
                confidence=0.74,
                normalized_transcript=normalized,
                needs_clarification=True,
                clarification_question="Which email should I create the reminder for? You can say email one, email two, or mention the sender or subject.",
                reminder_datetime_iso=reminder_iso.isoformat() if reminder_iso else None,
                source="rules",
            )
        return SmartVoiceResolution(
            intent=INTENT_START_REMINDER_CREATE,
            email_reference=last_explained_email_reference if "this" in normalized else None,
            confidence=0.82,
            normalized_transcript=normalized,
            needs_clarification=needs_time_clarification and reminder_iso is None,
            clarification_question="What time should I set the reminder for?" if needs_time_clarification and reminder_iso is None else None,
            reminder_datetime_iso=reminder_iso.isoformat() if reminder_iso else None,
            source="rules",
        )

    if any(marker in normalized for marker in ("end the call", "end call", "stop", "goodbye", "that's all", "thats all")):
        return SmartVoiceResolution(INTENT_END_CALL, None, 0.95, normalized, source="rules")
    if re.search(r"\bno\b", normalized) and not any(word in normalized for word in ("know", "notebook", "notification", "another")):
        return SmartVoiceResolution(INTENT_END_CALL, None, 0.92, normalized, source="rules")

    intent, question = _clarify_unknown(normalized)
    return SmartVoiceResolution(
        intent=intent,
        email_reference=None,
        confidence=0.25,
        normalized_transcript=normalized,
        needs_clarification=True,
        clarification_question=question,
        source="rules",
    )
