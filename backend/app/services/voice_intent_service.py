from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable

INTENT_DETAIL_EMAIL = "DETAIL_EMAIL"
INTENT_REPEAT_SUMMARY = "REPEAT_SUMMARY"
INTENT_END_CALL = "END_CALL"
INTENT_HELP = "HELP"
INTENT_TODAY_SUMMARY = "TODAY_SUMMARY"
INTENT_IMPORTANT_CHECK = "IMPORTANT_CHECK"
INTENT_START_EMAIL_REPLY = "START_EMAIL_REPLY"
INTENT_CAPTURE_REPLY_BODY = "CAPTURE_REPLY_BODY"
INTENT_CONFIRM_SEND_REPLY = "CONFIRM_SEND_REPLY"
INTENT_CANCEL_REPLY = "CANCEL_REPLY"
INTENT_EDIT_REPLY = "EDIT_REPLY"
INTENT_START_REMINDER_CREATE = "START_REMINDER_CREATE"
INTENT_CREATE_RECURRING_REMINDER = "CREATE_RECURRING_REMINDER"
INTENT_CAPTURE_REMINDER_DATETIME = "CAPTURE_REMINDER_DATETIME"
INTENT_CONFIRM_CREATE_REMINDER = "CONFIRM_CREATE_REMINDER"
INTENT_CANCEL_REMINDER_CREATE = "CANCEL_REMINDER_CREATE"
INTENT_UNKNOWN = "UNKNOWN"
LOOKUP_NUMBER = "number"
LOOKUP_SENDER = "sender"
LOOKUP_SUBJECT = "subject"
LOOKUP_KEYWORD = "keyword"
LOOKUP_LATEST = "latest"
LOOKUP_FIRST = "first"
LOOKUP_LAST = "last"
LOOKUP_UNKNOWN = "unknown"

NUMBER_WORDS = {
    "one": 1,
    "first": 1,
    "two": 2,
    "second": 2,
    "three": 3,
    "third": 3,
    "four": 4,
    "fourth": 4,
    "five": 5,
    "fifth": 5,
    "six": 6,
    "sixth": 6,
    "seven": 7,
    "seventh": 7,
    "eight": 8,
    "eighth": 8,
    "nine": 9,
    "ninth": 9,
    "ten": 10,
    "tenth": 10,
}

END_CALL_PHRASES = {
    "no",
    "no need",
    "nothing",
    "stop",
    "end call",
    "goodbye",
    "that's all",
    "thats all",
    "enough",
    "thank you",
    "bye",
}

REMINDER_CONFIRM_PHRASES = {
    "yes",
    "yeah",
    "yep",
    "ok",
    "okay",
    "save",
    "save it",
    "save this",
    "create",
    "create it",
    "create reminder",
    "do it",
    "yes save",
    "yes save it",
    "yes create it",
    "okay save it",
    "ok save it",
    "yeah save it",
    "yes please",
}

REMINDER_CANCEL_PHRASES = {
    "no",
    "no cancel",
    "cancel",
    "cancel it",
    "don't save",
    "dont save",
    "do not save",
    "stop",
    "stop it",
    "cancel reminder",
}

REPEAT_PHRASES = {
    "repeat",
    "repeat summary",
    "say again",
    "say that again",
    "read again",
    "tell again",
    "i did not understand",
    "i didn't understand",
    "can you repeat that",
    "repeat today summary",
    "repeat todays summary",
}

HELP_PHRASES = {
    "what can i say",
    "help",
    "options",
    "what can you do",
    "how can i ask",
    "what are my choices",
    "what are my options",
}

TODAY_PHRASES = {
    "what emails did i receive today",
    "which emails did i receive today",
    "what emails came today",
    "tell me todays emails",
    "tell me today's emails",
    "tell me todays mails",
    "tell me today's mails",
    "today mail",
    "todays mail",
    "today's mail",
    "read my todays mails",
    "read my today's mails",
    "today's emails",
    "todays emails",
    "today mails",
    "what is in today's mail",
}

IMPORTANT_PHRASES = {
    "is there any important mail",
    "what should i check first",
    "any urgent mail",
    "anything important today",
    "which email is important",
    "is anything important",
    "anything important",
    "any important mail",
}


@dataclass(slots=True)
class ParsedVoiceIntent:
    intent: str
    email_reference: int | None
    confidence: float
    normalized_transcript: str
    reason: str
    lookup_query: str | None = None
    lookup_type: str = LOOKUP_UNKNOWN
    sender_query: str | None = None
    subject_query: str | None = None
    keyword_query: str | None = None
    ordinal_reference: str | None = None
    reply_body: str | None = None
    target_email_reference: int | None = None
    target_lookup_type: str | None = None
    target_lookup_query: str | None = None
    reminder_text: str | None = None
    reminder_datetime_text: str | None = None
    reminder_datetime_iso: str | None = None
    digits: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def normalize_transcript(transcript: str | None) -> str:
    text = (transcript or "").strip().lower()
    text = text.replace("’", "'")
    text = re.sub(r"[^\w\s']", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _phrase_match(normalized: str, phrases: Iterable[str]) -> bool:
    for phrase in phrases:
        phrase_norm = normalize_transcript(phrase)
        if not phrase_norm:
            continue
        if re.search(rf"\b{re.escape(phrase_norm)}\b", normalized):
            return True
    return False


def _normalized_phrase_set(phrases: Iterable[str]) -> set[str]:
    return {normalize_transcript(phrase) for phrase in phrases if normalize_transcript(phrase)}


def _contains_word(normalized: str, word: str) -> bool:
    return bool(re.search(rf"\b{re.escape(word)}\b", normalized))


def _extract_email_reference(normalized: str) -> int | None:
    numeric_match = re.search(r"\b(\d+)\b", normalized)
    if numeric_match:
        return int(numeric_match.group(1))

    tokens = normalized.split()
    for index, token in enumerate(tokens):
        if token in NUMBER_WORDS:
            return NUMBER_WORDS[token]
        if token == "email" and index + 1 < len(tokens) and tokens[index + 1] in NUMBER_WORDS:
            return NUMBER_WORDS[tokens[index + 1]]
        if token == "mail" and index + 1 < len(tokens) and tokens[index + 1] in NUMBER_WORDS:
            return NUMBER_WORDS[tokens[index + 1]]
    return None


def _build_result(intent: str, normalized: str, email_reference: int | None, confidence: float, reason: str) -> ParsedVoiceIntent:
    return ParsedVoiceIntent(
        intent=intent,
        email_reference=email_reference,
        confidence=round(confidence, 2),
        normalized_transcript=normalized,
        reason=reason,
    )


def _build_detail_result(
    normalized: str,
    confidence: float,
    reason: str,
    email_reference: int | None = None,
    lookup_type: str = LOOKUP_UNKNOWN,
    lookup_query: str | None = None,
    sender_query: str | None = None,
    subject_query: str | None = None,
    keyword_query: str | None = None,
    ordinal_reference: str | None = None,
) -> ParsedVoiceIntent:
    return ParsedVoiceIntent(
        intent=INTENT_DETAIL_EMAIL,
        email_reference=email_reference,
        confidence=round(confidence, 2),
        normalized_transcript=normalized,
        reason=reason,
        lookup_query=lookup_query,
        lookup_type=lookup_type,
        sender_query=sender_query,
        subject_query=subject_query,
        keyword_query=keyword_query,
        ordinal_reference=ordinal_reference,
    )


def _build_reply_result(
    normalized: str,
    reason: str,
    confidence: float = 0.9,
    reply_body: str | None = None,
    target_email_reference: int | None = None,
    target_lookup_type: str | None = None,
    target_lookup_query: str | None = None,
    intent: str = INTENT_START_EMAIL_REPLY,
) -> ParsedVoiceIntent:
    return ParsedVoiceIntent(
        intent=intent,
        email_reference=None,
        confidence=round(confidence, 2),
        normalized_transcript=normalized,
        reason=reason,
        reply_body=reply_body,
        target_email_reference=target_email_reference,
        target_lookup_type=target_lookup_type,
        target_lookup_query=target_lookup_query,
    )


def _build_reminder_result(
    normalized: str,
    reason: str,
    confidence: float = 0.9,
    reminder_text: str | None = None,
    reminder_datetime_text: str | None = None,
    reminder_datetime_iso: str | None = None,
    intent: str = INTENT_START_REMINDER_CREATE,
) -> ParsedVoiceIntent:
    return ParsedVoiceIntent(
        intent=intent,
        email_reference=None,
        confidence=round(confidence, 2),
        normalized_transcript=normalized,
        reason=reason,
        reminder_text=reminder_text,
        reminder_datetime_text=reminder_datetime_text,
        reminder_datetime_iso=reminder_datetime_iso,
    )


def _normalize_lookup_text(text: str) -> str:
    text = normalize_transcript(text)
    text = re.sub(r"\b(?:the|my|a|an|this|that|today(?:'s)?|todays?)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_lookup_query(normalized: str) -> str | None:
    text = normalized
    patterns = [
        r"what did\s+(.+?)\s+send",
        r"(?:explain|read|describe|tell me about|tell me more about|what did .* send|what is|what's)\s+(?:the\s+)?(?:email|mail|message)\s+from\s+(.+)",
        r"(?:explain|read|describe|tell me about|tell me more about|what did .* send)\s+(.+)",
        r"(?:read|explain|describe|tell me about|tell me more about)\s+the\s+(.+?)\s+(?:email|mail|message)$",
        r"(?:read|explain|describe|tell me about|tell me more about)\s+(.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            candidate = _normalize_lookup_text(match.group(1))
            if candidate:
                return candidate
    return None


def _extract_reminder_datetime_text(normalized: str) -> str | None:
    patterns = [
        r"\b(?:tomorrow|today|tonight|next\s+\w+)\b.*",
        r"\b\d{1,2}[:.]\d{2}\s*(?:am|pm)?\b.*",
        r"\b\d{1,2}\s*(?:am|pm)\b.*",
        r"\b(?:in|after)\s+(?:a\s+)?(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:minute|minutes|min)\b.*",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return match.group(0).strip()
    return None


def _classify_lookup_type(normalized: str) -> tuple[str, str | None]:
    if re.search(r"\b(latest|newest|most recent)\b", normalized):
        return LOOKUP_LATEST, "latest"
    if re.search(r"\b(first|earliest|oldest)\b", normalized):
        return LOOKUP_FIRST, "first"
    if re.search(r"\b(last|final)\b", normalized):
        return LOOKUP_LAST, "last"
    if "from" in normalized:
        query = _extract_lookup_query(normalized)
        if query:
            return LOOKUP_SENDER, query
    query = _extract_lookup_query(normalized)
    if query:
        subject_markers = ("subject", "about", "kaggle", "assignment", "project", "auto sync", "summary", "notebook")
        if any(marker in query for marker in subject_markers):
            return LOOKUP_SUBJECT, query
        if any(marker in normalized for marker in ("subject", "about")):
            return LOOKUP_SUBJECT, query
        return LOOKUP_KEYWORD, query
    return LOOKUP_UNKNOWN, None


def parse_voice_intent(transcript: str | None) -> ParsedVoiceIntent:
    normalized = normalize_transcript(transcript)
    if not normalized:
        return ParsedVoiceIntent(
            intent=INTENT_UNKNOWN,
            email_reference=None,
            confidence=0.2,
            normalized_transcript=normalized,
            reason="empty transcript",
        )

    if normalized in _normalized_phrase_set(HELP_PHRASES):
        return _build_result(INTENT_HELP, normalized, None, 0.95, "matched help phrase")

    if normalized in _normalized_phrase_set(TODAY_PHRASES):
        return _build_result(INTENT_TODAY_SUMMARY, normalized, None, 0.94, "matched today-summary phrase")

    if normalized in _normalized_phrase_set(IMPORTANT_PHRASES):
        return _build_result(INTENT_IMPORTANT_CHECK, normalized, None, 0.9, "matched important-check phrase")

    if re.fullmatch(r"(yes|yes send it|send it|confirm|okay send|ok send|send)", normalized):
        return _build_reply_result(normalized, "matched reply confirm phrase", confidence=0.97, intent=INTENT_CONFIRM_SEND_REPLY)
    if re.fullmatch(r"(cancel|don't send|dont send|discard|stop sending)", normalized):
        return _build_reply_result(normalized, "matched reply cancel phrase", confidence=0.97, intent=INTENT_CANCEL_REPLY)
    if _phrase_match(normalized, {"change it", "edit it", "modify reply"}):
        return _build_reply_result(normalized, "matched reply edit phrase", confidence=0.95, intent=INTENT_EDIT_REPLY)
    reply_markers = [
        "reply to this email",
        "send a reply",
        "reply to email",
        "reply to the latest email",
        "reply to the first email",
        "reply to the last email",
        "respond to this mail",
        "respond to the latest email",
        "respond to the first email",
        "respond to the last email",
        "reply saying",
        "respond with",
        "reply",
    ]
    if _phrase_match(normalized, reply_markers):
        body = None
        target_ref = _extract_email_reference(normalized)
        reply_match = re.search(r"\b(?:reply saying|respond with|send reply saying|send a reply saying|reply to this email saying|reply to email number \w+ saying|reply to email saying)\s+(.+)$", normalized)
        if reply_match:
            body = reply_match.group(1).strip()
        elif "saying" in normalized:
            body = normalized.split("saying", 1)[1].strip() or None
        target_lookup_type = None
        target_lookup_query = None
        if "latest" in normalized:
            target_lookup_type = LOOKUP_LATEST
            target_lookup_query = "latest"
        elif "first" in normalized:
            target_lookup_type = LOOKUP_FIRST
            target_lookup_query = "first"
        elif "last" in normalized:
            target_lookup_type = LOOKUP_LAST
            target_lookup_query = "last"
        else:
            target_lookup_type, target_lookup_query = _classify_lookup_type(normalized)
        if target_lookup_type == LOOKUP_UNKNOWN and ("from" in normalized or "about" in normalized or "subject" in normalized):
            target_lookup_query = _extract_lookup_query(normalized)
        return _build_reply_result(
            normalized,
            "matched reply command",
            confidence=0.9 if body else 0.88,
            reply_body=body,
            target_email_reference=target_ref,
            target_lookup_type=target_lookup_type,
            target_lookup_query=target_lookup_query,
        )

    reminder_markers = [
        "remind me",
        "remind about",
        "create reminder",
        "set a reminder",
        "set reminder",
        "add reminder",
        "reminder for this email",
        "reminder for email",
        "reminder for this",
        "remind me this email",
        "remind me about this email",
        "remind about this email",
        "reminder about this email",
        "set reminder for this email",
        "remind me about mail",
        "remind me about this mail",
    ]
    if _phrase_match(normalized, reminder_markers):
        reminder_text = _extract_lookup_query(normalized)
        reminder_datetime_text = _extract_reminder_datetime_text(normalized)
        return _build_reminder_result(
            normalized,
            "matched reminder command",
            confidence=0.88 if reminder_datetime_text else 0.82,
            reminder_text=reminder_text,
            reminder_datetime_text=reminder_datetime_text,
        )

    if _contains_word(normalized, "remind") and not _contains_word(normalized, "reminderless"):
        reminder_datetime_text = _extract_reminder_datetime_text(normalized)
        if reminder_datetime_text is None:
            reminder_datetime_text = _extract_lookup_query(normalized)
        return _build_reminder_result(
            normalized,
            "matched reminder keyword",
            confidence=0.8 if reminder_datetime_text else 0.75,
            reminder_text=_extract_lookup_query(normalized),
            reminder_datetime_text=reminder_datetime_text,
        )

    if normalized == "no":
        return _build_result(INTENT_END_CALL, normalized, None, 0.98, "matched standalone no")
    if normalized in END_CALL_PHRASES - {"no"}:
        return _build_result(INTENT_END_CALL, normalized, None, 0.97, "matched end-call phrase")
    if re.search(r"\bno\b", normalized) and not any(word in normalized for word in ("know", "notebook", "notification", "another")):
        return _build_result(INTENT_END_CALL, normalized, None, 0.92, "matched word-boundary no")

    detail_markers = [
        "explain",
        "explain in detail",
        "detail",
        "details",
        "in detail",
        "details of",
        "tell me more",
        "read",
        "open",
        "describe",
        "what is",
        "what's",
        "what is email",
        "what is the",
        "tell me about",
        "know more about",
        "more about",
    ]

    lookup_type, lookup_query = _classify_lookup_type(normalized)
    if lookup_type in {LOOKUP_LATEST, LOOKUP_FIRST, LOOKUP_LAST}:
        return _build_detail_result(
            normalized=normalized,
            confidence=0.9,
            reason=f"matched ordinal lookup {lookup_type}",
            lookup_type=lookup_type,
            lookup_query=lookup_type,
            ordinal_reference=lookup_type,
        )
    email_reference = _extract_email_reference(normalized)
    if email_reference is not None and _phrase_match(normalized, detail_markers):
        return _build_detail_result(
            normalized=normalized,
            confidence=0.92,
            reason="matched detail phrase with number",
            email_reference=email_reference,
            lookup_type=LOOKUP_NUMBER,
            lookup_query=str(email_reference),
            ordinal_reference=str(email_reference),
        )
    if lookup_type == LOOKUP_SENDER:
        return _build_detail_result(
            normalized=normalized,
            confidence=0.85,
            reason="matched sender lookup",
            lookup_type=lookup_type,
            lookup_query=lookup_query,
            sender_query=lookup_query,
        )
    if lookup_type == LOOKUP_SUBJECT:
        return _build_detail_result(
            normalized=normalized,
            confidence=0.84,
            reason="matched subject lookup",
            lookup_type=lookup_type,
            lookup_query=lookup_query,
            subject_query=lookup_query,
        )
    if lookup_type == LOOKUP_KEYWORD:
        return _build_detail_result(
            normalized=normalized,
            confidence=0.8,
            reason="matched keyword lookup",
            lookup_type=lookup_type,
            lookup_query=lookup_query,
            keyword_query=lookup_query,
        )
    if _phrase_match(normalized, detail_markers) and (_contains_word(normalized, "email") or _contains_word(normalized, "mail") or _contains_word(normalized, "message")):
        return _build_detail_result(
            normalized=normalized,
            confidence=0.8,
            reason="matched detail phrase without number",
            lookup_type=LOOKUP_UNKNOWN,
            lookup_query=_extract_lookup_query(normalized),
        )

    repeat_markers = [
        "repeat summary",
        "repeat",
        "say again",
        "say that again",
        "read again",
        "tell again",
        "i did not understand",
        "i didn't understand",
        "can you repeat that",
        "repeat that",
        "say it again",
    ]
    if _phrase_match(normalized, repeat_markers):
        return _build_result(INTENT_REPEAT_SUMMARY, normalized, None, 0.93, "matched repeat phrase")

    if _contains_word(normalized, "repeat") and not _contains_word(normalized, "irrepeatable"):
        return _build_result(INTENT_REPEAT_SUMMARY, normalized, None, 0.82, "matched repeat keyword")

    if _contains_word(normalized, "know") and not _phrase_match(normalized, {"i did not know"}):
        return _build_result(INTENT_UNKNOWN, normalized, None, 0.2, "contains know but not an intent")

    return ParsedVoiceIntent(
        intent=INTENT_UNKNOWN,
        email_reference=None,
        confidence=0.2,
        normalized_transcript=normalized,
        reason="no matching rule",
    )
