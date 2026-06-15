from __future__ import annotations

from types import SimpleNamespace

from app.config import settings
from app.services import gemini_email_agent_service as gemini_service


def _sample_email() -> SimpleNamespace:
    return SimpleNamespace(
        subject="Re: Your application update",
        sender="Anisha <anishathahir08@gmail.com>",
        plain_body="Please review the attached update and reply by tomorrow.",
    )


def test_generate_understanding_summary_english_mocked(monkeypatch) -> None:
    monkeypatch.setattr(settings, "email_summary_provider", "gemini", raising=False)
    monkeypatch.setattr(settings, "gemini_api_key", "test-key", raising=False)
    monkeypatch.setattr(
        gemini_service,
        "_call_gemini",
        lambda prompt: {
            "short_summary": "The email asks for review and a reply.",
            "important_points": ["review", "reply tomorrow"],
            "action_required": "Reply is needed.",
            "deadline_or_date": "tomorrow",
            "reply_needed": True,
            "suggested_reminder": "Reply tomorrow",
            "language_used": "english",
        },
    )

    result = gemini_service.generate_understanding_summary(
        subject=_sample_email().subject,
        sender=_sample_email().sender,
        body=_sample_email().plain_body,
        preferred_language="english",
    )

    assert result["short_summary"] == "The email asks for review and a reply."
    assert result["important_points"] == ["review", "reply tomorrow"]
    assert result["action_required"] == "Reply is needed."
    assert result["reply_needed"] is True
    assert result["language_used"] == "english"


def test_generate_understanding_summary_tanglish_mocked(monkeypatch) -> None:
    monkeypatch.setattr(settings, "email_summary_provider", "gemini", raising=False)
    monkeypatch.setattr(settings, "gemini_api_key", "test-key", raising=False)
    monkeypatch.setattr(
        gemini_service,
        "_call_gemini",
        lambda prompt: {
            "short_summary": "Indha email pathi important update irukku.",
            "important_points": ["update"],
            "action_required": "Reply panna vendum.",
            "deadline_or_date": None,
            "reply_needed": False,
            "suggested_reminder": None,
            "language_used": "tanglish",
        },
    )

    result = gemini_service.generate_understanding_summary(
        subject=_sample_email().subject,
        sender=_sample_email().sender,
        body=_sample_email().plain_body,
        preferred_language="tanglish",
    )

    assert result["short_summary"] == "Indha email pathi important update irukku."
    assert result["language_used"] == "tanglish"


def test_generate_detailed_explanation_mocked(monkeypatch) -> None:
    monkeypatch.setattr(settings, "email_summary_provider", "gemini", raising=False)
    monkeypatch.setattr(settings, "gemini_api_key", "test-key", raising=False)
    monkeypatch.setattr(
        gemini_service,
        "_call_gemini",
        lambda prompt: {
            "detailed_explanation": "This email asks you to review the update and reply by tomorrow.",
            "important_points": ["review update"],
            "action_items": ["reply"],
            "deadline_or_date": "tomorrow",
            "language_used": "english",
        },
    )

    result = gemini_service.generate_detailed_explanation(
        subject=_sample_email().subject,
        sender=_sample_email().sender,
        body=_sample_email().plain_body,
        preferred_language="english",
    )

    assert result["detailed_explanation"].startswith("This email asks you")
    assert result["action_items"] == ["reply"]
    assert result["language_used"] == "english"


def test_draft_reply_mocked(monkeypatch) -> None:
    monkeypatch.setattr(settings, "email_summary_provider", "gemini", raising=False)
    monkeypatch.setattr(settings, "gemini_api_key", "test-key", raising=False)
    monkeypatch.setattr(
        gemini_service,
        "_call_gemini",
        lambda prompt: {
            "reply_draft": "Hi, thanks for the update. I will review it and reply soon.",
            "tone": "friendly",
            "safety_note": "Draft only.",
            "language_used": "english",
        },
    )

    result = gemini_service.draft_reply(
        subject=_sample_email().subject,
        sender=_sample_email().sender,
        body=_sample_email().plain_body,
        user_reply_instruction="Thanks, I will review this",
        preferred_language="english",
    )

    assert result["reply_draft"].startswith("Hi, thanks")
    assert result["tone"] == "friendly"
    assert "Draft only" in result["safety_note"]


def test_extract_reminder_intent_mocked(monkeypatch) -> None:
    monkeypatch.setattr(settings, "email_summary_provider", "gemini", raising=False)
    monkeypatch.setattr(settings, "gemini_api_key", "test-key", raising=False)
    monkeypatch.setattr(
        gemini_service,
        "_call_gemini",
        lambda prompt: {
            "wants_reminder": True,
            "reminder_title": "Follow up on application",
            "reminder_datetime_text": "tomorrow at 10 AM",
            "reminder_context": "Reply requested",
            "confidence": 0.91,
            "language_used": "english",
        },
    )

    result = gemini_service.extract_reminder_intent(
        subject=_sample_email().subject,
        sender=_sample_email().sender,
        body=_sample_email().plain_body,
        user_request_text="Tomorrow at 10 AM remind me about this email",
        current_datetime="2026-06-15T10:00:00+00:00",
        timezone_name="Asia/Kolkata",
        preferred_language="english",
    )

    assert result["wants_reminder"] is True
    assert result["reminder_title"] == "Follow up on application"
    assert result["confidence"] == 0.91


def test_missing_api_key_falls_back_without_calling_gemini(monkeypatch) -> None:
    monkeypatch.setattr(settings, "email_summary_provider", "gemini", raising=False)
    monkeypatch.setattr(settings, "gemini_api_key", "", raising=False)
    called = {"value": False}

    def _should_not_run(prompt):
        called["value"] = True
        raise AssertionError("Gemini should not be called without API key")

    monkeypatch.setattr(gemini_service, "_call_gemini", _should_not_run)

    result = gemini_service.generate_understanding_summary(
        subject="Hello",
        sender="Sender <sender@example.com>",
        body="Please review this.",
        preferred_language="english",
    )

    assert called["value"] is False
    assert "Sender" in result["short_summary"]


def test_gemini_failure_falls_back(monkeypatch) -> None:
    monkeypatch.setattr(settings, "email_summary_provider", "gemini", raising=False)
    monkeypatch.setattr(settings, "gemini_api_key", "test-key", raising=False)
    monkeypatch.setattr(gemini_service, "_call_gemini", lambda prompt: (_ for _ in ()).throw(RuntimeError("boom")))

    result = gemini_service.generate_detailed_explanation(
        subject="Hello",
        sender="Sender <sender@example.com>",
        body="Please review this.",
        preferred_language="english",
    )

    assert "Sender" in result["detailed_explanation"]


def test_empty_email_content_falls_back(monkeypatch) -> None:
    monkeypatch.setattr(settings, "email_summary_provider", "existing", raising=False)
    monkeypatch.setattr(settings, "gemini_api_key", "", raising=False)

    summary = gemini_service.generate_understanding_summary(
        subject="",
        sender="",
        body="",
        preferred_language="tanglish",
    )
    detail = gemini_service.generate_detailed_explanation(
        subject="",
        sender="",
        body="",
        preferred_language="tanglish",
    )
    reply = gemini_service.draft_reply(
        subject="",
        sender="",
        body="",
        user_reply_instruction="",
        preferred_language="tanglish",
    )
    reminder = gemini_service.extract_reminder_intent(
        subject="",
        sender="",
        body="",
        user_request_text="",
        current_datetime="2026-06-15T10:00:00+00:00",
        timezone_name="Asia/Kolkata",
        preferred_language="tanglish",
    )

    assert summary["short_summary"]
    assert detail["detailed_explanation"]
    assert reply["reply_draft"]
    assert reminder["wants_reminder"] is False
    assert reminder["language_used"] == "tanglish"
