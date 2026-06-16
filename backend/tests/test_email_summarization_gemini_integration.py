from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.config import settings
from app.database.session import SessionLocal
from app.models.email_message import EmailMessage
from app.models.email_summary import EmailSummary
from app.models.user import User
from app.services import email_summarization_service as summary_service


def _create_email(db, user: User, suffix: str) -> EmailMessage:
    email = EmailMessage(
        user_id=user.id,
        gmail_message_id=f"gemini-summary-{suffix}-{uuid4()}",
        gmail_thread_id=f"thread-{uuid4()}",
        sender="mentor@example.com",
        recipient=user.email,
        subject="Project update",
        snippet="Please review the update.",
        plain_body="Please review the update and reply tomorrow.",
        html_body=None,
        received_at=datetime.now(timezone.utc),
        has_attachments=False,
        attachment_metadata=None,
        is_read_from_gmail=True,
        is_summarized=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(email)
    db.flush()
    return email


def _cleanup_email(db, email: EmailMessage) -> None:
    db.query(EmailSummary).filter(EmailSummary.email_message_id == email.id).delete(synchronize_session=False)
    db.delete(email)
    db.commit()


def test_gemini_summary_used_when_enabled(monkeypatch) -> None:
    db = SessionLocal()
    email = None
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        assert user is not None
        email = _create_email(db, user, "enabled")
        monkeypatch.setattr(settings, "email_summary_provider", "gemini", raising=False)
        monkeypatch.setattr(settings, "gemini_api_key", "test-key", raising=False)
        monkeypatch.setattr(settings, "default_summary_language", "tanglish", raising=False)
        monkeypatch.setattr(
            summary_service,
            "generate_understanding_summary",
            lambda **kwargs: {
                "short_summary": "Gemini short summary",
                "important_points": ["Point 1", "Point 2"],
                "action_required": "Reply needed",
                "deadline_or_date": "tomorrow",
                "reply_needed": True,
                "suggested_reminder": "Follow up tomorrow",
                "language_used": "tanglish",
            },
        )

        result = summary_service.summarize_email_ids(db, user, [email.id])
        db.refresh(email)
        summary = db.query(EmailSummary).filter(EmailSummary.email_message_id == email.id).first()

        assert result["processed_count"] == 1
        assert result["success_count"] == 1
        assert email.is_summarized is True
        assert summary is not None
        assert summary.short_summary == "Gemini short summary"
        assert "Point 1" in summary.detailed_summary
        assert summary.action_required_text == "Reply needed"
    finally:
        if email is not None:
            _cleanup_email(db, email)
        db.close()


def test_fallback_used_when_gemini_disabled(monkeypatch) -> None:
    db = SessionLocal()
    email = None
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        assert user is not None
        email = _create_email(db, user, "disabled")
        monkeypatch.setattr(settings, "email_summary_provider", "existing", raising=False)
        monkeypatch.setattr(settings, "gemini_api_key", "", raising=False)

        called = {"value": False}

        def _legacy(email_obj):
            called["value"] = True
            return {
                "short_summary": "Fallback summary",
                "detailed_summary": "Fallback summary detail",
                "action_required_text": "No clear action requested.",
                "attachment_note": "No attachments mentioned.",
            }

        monkeypatch.setattr(summary_service, "_legacy_generate_summary", _legacy)

        result = summary_service.summarize_email_ids(db, user, [email.id])
        db.refresh(email)
        summary = db.query(EmailSummary).filter(EmailSummary.email_message_id == email.id).first()

        assert called["value"] is True
        assert result["success_count"] == 1
        assert summary is not None
        assert summary.short_summary == "Fallback summary"
        assert summary.detailed_summary == "Fallback summary detail"
    finally:
        if email is not None:
            _cleanup_email(db, email)
        db.close()


def test_fallback_used_when_gemini_fails(monkeypatch) -> None:
    db = SessionLocal()
    email = None
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        assert user is not None
        email = _create_email(db, user, "fails")
        monkeypatch.setattr(settings, "email_summary_provider", "gemini", raising=False)
        monkeypatch.setattr(settings, "gemini_api_key", "test-key", raising=False)
        monkeypatch.setattr(summary_service, "generate_understanding_summary", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
        monkeypatch.setattr(
            summary_service,
            "_legacy_generate_summary",
            lambda email_obj: {
                "short_summary": "Fallback after Gemini error",
                "detailed_summary": "Fallback after Gemini error detail",
                "action_required_text": "No clear action requested.",
                "attachment_note": "No attachments mentioned.",
            },
        )

        result = summary_service.summarize_email_ids(db, user, [email.id])
        db.refresh(email)
        summary = db.query(EmailSummary).filter(EmailSummary.email_message_id == email.id).first()

        assert result["success_count"] == 1
        assert summary is not None
        assert summary.short_summary == "Fallback after Gemini error"
        assert summary.detailed_summary == "Fallback after Gemini error detail"
    finally:
        if email is not None:
            _cleanup_email(db, email)
        db.close()


def test_fallback_summary_is_voice_friendly_when_provider_disabled(monkeypatch) -> None:
    db = SessionLocal()
    email = None
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        assert user is not None
        email = _create_email(db, user, "friendly")
        email.subject = "Gentil hospital reminder"
        email.sender = "Gentil hospital <reminder@gentilhospital.example>"
        email.plain_body = "Please review your hospital follow-up reminder."
        db.add(email)
        db.commit()

        monkeypatch.setattr(settings, "email_summary_provider", "existing", raising=False)
        monkeypatch.setattr(settings, "gemini_api_key", "", raising=False)

        result = summary_service.summarize_email_ids(db, user, [email.id])
        summary = db.query(EmailSummary).filter(EmailSummary.email_message_id == email.id).first()

        assert result["success_count"] == 1
        assert summary is not None
        assert summary.short_summary
        assert "Gentil hospital" in summary.short_summary or "Email received about" in summary.short_summary
        assert "follow-up" in summary.detailed_summary.lower()
        assert "from" not in summary.short_summary.lower() or "email received about" in summary.short_summary.lower()
    finally:
        if email is not None:
            _cleanup_email(db, email)
        db.close()


def test_gemini_failure_logs_safe_fallback(monkeypatch, caplog) -> None:
    db = SessionLocal()
    email = None
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        assert user is not None
        email = _create_email(db, user, "log")
        monkeypatch.setattr(settings, "email_summary_provider", "gemini", raising=False)
        monkeypatch.setattr(settings, "gemini_api_key", "test-key", raising=False)
        monkeypatch.setattr(summary_service, "generate_understanding_summary", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

        with caplog.at_level("WARNING"):
            summary_service.summarize_email_ids(db, user, [email.id])

        assert any("Gemini summary fallback used" in record.message for record in caplog.records)
    finally:
        if email is not None:
            _cleanup_email(db, email)
        db.close()
