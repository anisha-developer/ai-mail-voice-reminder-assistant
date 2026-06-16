from __future__ import annotations

import json
from typing import Any
from email.utils import parseaddr
from urllib import error, request

from app.config import settings


SUPPORTED_LANGUAGES = {"english", "tamil", "tanglish"}


def _normalize_language(value: str | None) -> str:
    normalized = (value or settings.default_summary_language or "english").strip().lower()
    if normalized not in SUPPORTED_LANGUAGES:
        return "english"
    return normalized


def _clean_text(value: str | None) -> str:
    return (value or "").replace("\x00", " ").strip()


def _body_text(body: str | None) -> str:
    cleaned = _clean_text(body)
    return cleaned[:4000] if cleaned else ""


def _sender_label(sender: str | None) -> str:
    sender_text = _clean_text(sender)
    if not sender_text:
        return "Unknown sender"
    display_name, _ = parseaddr(sender_text)
    if display_name.strip():
        return display_name.strip()
    if "<" in sender_text and ">" in sender_text:
        prefix = sender_text.split("<", 1)[0].strip()
        if prefix:
            return prefix
    return "Unknown sender"


def _default_summary_payload(subject: str | None, sender: str | None, body: str | None, language: str) -> dict[str, Any]:
    subject_text = _clean_text(subject) or "No subject"
    body_text = _body_text(body)
    summary_base = f"Email received about {subject_text}. It may need review based on the message content."
    if language == "tamil":
        summary_base = f"Email received about {subject_text}. It may need review based on the message content."
    elif language == "tanglish":
        summary_base = f"Indha email {subject_text} pathi vandhurukku. Message content-a paathu review panna vendiyadhu."
    if body_text:
        summary_base = f"{summary_base} {body_text[:120]}".strip()
    important_points = [subject_text]
    if body_text:
        important_points.append(body_text[:120])
    return {
        "short_summary": summary_base,
        "important_points": important_points[:3],
        "action_required": "unclear" if not body_text else "review",
        "deadline_or_date": None,
        "reply_needed": False,
        "suggested_reminder": None,
        "language_used": language,
    }


def _default_detail_payload(subject: str | None, sender: str | None, body: str | None, language: str) -> dict[str, Any]:
    subject_text = _clean_text(subject) or "No subject"
    body_text = _body_text(body)
    if language == "tamil":
        explanation = f"Email received about {subject_text}. It may need review."
    elif language == "tanglish":
        explanation = f"Indha email {subject_text} pathi vandhurukku. Review panna vendiya message."
    else:
        explanation = f"Email received about {subject_text}. It may need review based on the message content."
    if body_text:
        explanation = f"{explanation} Details: {body_text[:220]}"
    return {
        "detailed_explanation": explanation,
        "important_points": [subject_text] + ([body_text[:120]] if body_text else []),
        "action_items": [],
        "deadline_or_date": None,
        "language_used": language,
    }


def _default_reply_payload(subject: str | None, sender: str | None, instruction: str | None, language: str) -> dict[str, Any]:
    subject_text = _clean_text(subject) or "No subject"
    sender_text = _clean_text(sender) or "Unknown sender"
    instruction_text = _clean_text(instruction)
    if language == "tamil":
        reply = f"Hello {sender_text}, regarding {subject_text}, {instruction_text or 'thanks for your email.'}"
    elif language == "tanglish":
        reply = f"Vanakkam {sender_text}, {subject_text} ku neenga sonnadha pathi reply panren."
    else:
        reply = f"Hi {sender_text}, regarding {subject_text}, {instruction_text or 'thanks for your email.'}"
    return {
        "reply_draft": reply,
        "tone": "friendly",
        "safety_note": "Draft only. Do not send without confirmation.",
        "language_used": language,
    }


def _default_reminder_payload(
    subject: str | None,
    sender: str | None,
    body: str | None,
    user_request_text: str | None,
    current_datetime: str | None,
    timezone_name: str | None,
    language: str,
) -> dict[str, Any]:
    subject_text = _clean_text(subject) or "No subject"
    sender_text = _clean_text(sender) or "Unknown sender"
    request_text = _clean_text(user_request_text)
    reminder_title = f"Follow up on {subject_text}"
    reminder_context = f"Email from {sender_text}"
    if body := _body_text(body):
        reminder_context = f"{reminder_context}: {body[:120]}"
    if language == "tamil":
        reminder_title = f"Follow up about {subject_text}"
    elif language == "tanglish":
        reminder_title = f"{subject_text} pathi follow up pannunga"
    return {
        "wants_reminder": bool(request_text),
        "reminder_title": reminder_title,
        "reminder_datetime_text": request_text or current_datetime or "",
        "reminder_context": reminder_context,
        "confidence": 0.35 if request_text else 0.0,
        "language_used": language,
        "timezone": timezone_name or "UTC",
    }


def _build_gemini_request(prompt: str) -> dict[str, Any]:
    return {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 512,
            "responseMimeType": "application/json",
        },
    }


def _call_gemini(prompt: str) -> dict[str, Any]:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is missing")

    model_name = "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={settings.gemini_api_key}"
    req = request.Request(
        url,
        data=json.dumps(_build_gemini_request(prompt)).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode())
    except error.HTTPError as exc:
        raise RuntimeError(f"Gemini API failure: {exc.reason}") from exc
    except Exception as exc:
        raise RuntimeError("Gemini API failure") from exc

    candidates = data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini API failure")
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    if not text.strip():
        raise RuntimeError("Gemini API failure")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Gemini API failure") from exc


def _should_use_gemini() -> bool:
    return settings.email_summary_provider.lower().strip() == "gemini" and bool(settings.gemini_api_key)


def _prompt_intro(language: str) -> str:
    return (
        "You are the understanding brain for an email assistant. "
        "Understand the email meaning. Do not just copy the email. "
        "Identify purpose, important points, action needed, deadline/date/time if present, and whether reply or reminder is useful. "
        "Write in a voice-friendly way using simple user-friendly words. "
        "For short summaries, use 1 to 2 clear sentences. For detailed explanations, use 3 to 5 useful sentences. "
        "Do not use awkward phrases like 'kitta irundhu'. Do not invent facts. If unclear, say unclear. "
        "Do not give medical or diet advice unless the email explicitly contains such content. "
        f"Return only JSON. Use selected language: {language}."
    )


def _fallback_or_gemini(
    *,
    prompt: str,
    fallback_payload: dict[str, Any],
    expected_keys: set[str],
) -> dict[str, Any]:
    if not _should_use_gemini():
        return fallback_payload
    try:
        result = _call_gemini(prompt)
    except Exception:
        return fallback_payload
    if not isinstance(result, dict):
        return fallback_payload
    normalized = dict(fallback_payload)
    for key in expected_keys:
        if key in result:
            normalized[key] = result[key]
    for key, value in result.items():
        if key not in normalized and key in expected_keys:
            normalized[key] = value
    normalized["language_used"] = fallback_payload.get("language_used") or "english"
    return normalized


def generate_understanding_summary(
    *,
    subject: str | None,
    sender: str | None,
    body: str | None,
    preferred_language: str | None = None,
) -> dict[str, Any]:
    language = _normalize_language(preferred_language)
    fallback = _default_summary_payload(subject, sender, body, language)
    prompt = (
        f"{_prompt_intro(language)}\n"
        "Task: create a concise understanding summary.\n"
        "Make the summary useful for a phone call. Explain the purpose or meaning of the email, not just the sender and subject.\n"
        f"Subject: {_clean_text(subject) or 'No subject'}\n"
        f"Sender: {_clean_text(sender) or 'Unknown sender'}\n"
        f"Body: {_body_text(body) or 'Email body was empty.'}\n"
        "Return JSON with keys: short_summary, important_points, action_required, deadline_or_date, reply_needed, suggested_reminder, language_used."
    )
    return _fallback_or_gemini(
        prompt=prompt,
        fallback_payload=fallback,
        expected_keys={"short_summary", "important_points", "action_required", "deadline_or_date", "reply_needed", "suggested_reminder", "language_used"},
    )


def generate_detailed_explanation(
    *,
    subject: str | None,
    sender: str | None,
    body: str | None,
    preferred_language: str | None = None,
) -> dict[str, Any]:
    language = _normalize_language(preferred_language)
    fallback = _default_detail_payload(subject, sender, body, language)
    prompt = (
        f"{_prompt_intro(language)}\n"
        "Task: create a detailed explanation that is still voice-friendly.\n"
        "Explain the meaning clearly in 3 to 5 simple sentences. Mention any action, deadline, or reminder value if present.\n"
        f"Subject: {_clean_text(subject) or 'No subject'}\n"
        f"Sender: {_clean_text(sender) or 'Unknown sender'}\n"
        f"Body: {_body_text(body) or 'Email body was empty.'}\n"
        "Return JSON with keys: detailed_explanation, important_points, action_items, deadline_or_date, language_used."
    )
    return _fallback_or_gemini(
        prompt=prompt,
        fallback_payload=fallback,
        expected_keys={"detailed_explanation", "important_points", "action_items", "deadline_or_date", "language_used"},
    )


def draft_reply(
    *,
    subject: str | None,
    sender: str | None,
    body: str | None,
    user_reply_instruction: str | None,
    preferred_language: str | None = None,
) -> dict[str, Any]:
    language = _normalize_language(preferred_language)
    fallback = _default_reply_payload(subject, sender, user_reply_instruction, language)
    prompt = (
        f"{_prompt_intro(language)}\n"
        "Task: draft a reply only. Do not send the email.\n"
        f"Subject: {_clean_text(subject) or 'No subject'}\n"
        f"Sender: {_clean_text(sender) or 'Unknown sender'}\n"
        f"Body: {_body_text(body) or 'Email body was empty.'}\n"
        f"User instruction: {_clean_text(user_reply_instruction) or 'Hi.'}\n"
        "Return JSON with keys: reply_draft, tone, safety_note, language_used."
    )
    return _fallback_or_gemini(
        prompt=prompt,
        fallback_payload=fallback,
        expected_keys={"reply_draft", "tone", "safety_note", "language_used"},
    )


def extract_reminder_intent(
    *,
    subject: str | None,
    sender: str | None,
    body: str | None,
    user_request_text: str | None,
    current_datetime: str | None = None,
    timezone_name: str | None = None,
    preferred_language: str | None = None,
) -> dict[str, Any]:
    language = _normalize_language(preferred_language)
    fallback = _default_reminder_payload(subject, sender, body, user_request_text, current_datetime, timezone_name, language)
    prompt = (
        f"{_prompt_intro(language)}\n"
        "Task: extract reminder intent only. Do not create the reminder.\n"
        f"Subject: {_clean_text(subject) or 'No subject'}\n"
        f"Sender: {_clean_text(sender) or 'Unknown sender'}\n"
        f"Body: {_body_text(body) or 'Email body was empty.'}\n"
        f"User request: {_clean_text(user_request_text) or 'No request provided.'}\n"
        f"Current datetime: {current_datetime or 'unknown'}\n"
        f"Timezone: {timezone_name or 'UTC'}\n"
        "Return JSON with keys: wants_reminder, reminder_title, reminder_datetime_text, reminder_context, confidence, language_used."
    )
    return _fallback_or_gemini(
        prompt=prompt,
        fallback_payload=fallback,
        expected_keys={"wants_reminder", "reminder_title", "reminder_datetime_text", "reminder_context", "confidence", "language_used"},
    )
