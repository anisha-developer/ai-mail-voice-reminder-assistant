from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from app.config import settings
from app.database.session import SessionLocal
from app.models.email_message import EmailMessage
from app.models.email_summary import EmailSummary
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.user import User
from app.services.make_elevenlabs_call_service import send_mail_summary_call_to_make


def _user() -> User:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        assert user is not None
        return user
    finally:
        db.close()


def _call_log_with_summary() -> tuple[int, int, int]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        assert user is not None
        message = EmailMessage(
            user_id=user.id,
            gmail_message_id=f"make-test-{uuid4()}",
            gmail_thread_id=None,
            sender="Portfolio Contact Form <notify+abc@example.com>",
            recipient=user.email,
            subject="Portfolio inquiry",
            snippet="Please review the attached portfolio",
            plain_body="Forwarded message and raw body should not leak.",
            html_body=None,
            received_at=datetime.now(timezone.utc),
            has_attachments=False,
            attachment_metadata=None,
            is_read_from_gmail=True,
            is_summarized=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(message)
        db.flush()
        summary = EmailSummary(
            user_id=user.id,
            email_message_id=message.id,
            sender=message.sender,
            subject=message.subject,
            short_summary="Portfolio inquiry mail needs review.",
            detailed_summary="---------- Forwarded message ---------\nFrom: Portfolio Contact Form <notify+abc@example.com>\nPlease review the attached portfolio and reply if needed.",
            action_required_text="Please review and respond.",
            attachment_note=None,
            summary_status="completed",
            error_message=None,
            is_delivered_in_mail_call=False,
            delivered_at=None,
            mail_call_log_id=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(summary)
        db.flush()
        call_log = MailSummaryCallLog(
            user_id=user.id,
            call_type="mail_summary",
            call_status="prepared",
            call_date=datetime.now(timezone.utc).date(),
            call_time=datetime.now(timezone.utc).time().replace(microsecond=0),
            summary_count=1,
            script_text="Test script",
            delivery_status="pending",
            delivered_summary_ids=json.dumps([summary.id]),
            failure_reason=None,
            provider=None,
            provider_call_id=None,
            to_phone_number=user.phone_number,
            from_phone_number=None,
            call_started_at=None,
            call_completed_at=None,
            call_duration_seconds=None,
            provider_status=None,
            provider_error_message=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(call_log)
        db.commit()
        db.refresh(call_log)
        return call_log.id, summary.id, message.id
    finally:
        db.close()


def _cleanup(call_log_id: int, summary_id: int, message_id: int) -> None:
    db = SessionLocal()
    try:
        db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).delete(synchronize_session=False)
        db.query(EmailSummary).filter(EmailSummary.id == summary_id).delete(synchronize_session=False)
        db.query(EmailMessage).filter(EmailMessage.id == message_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_payload_shape_and_sanitization(monkeypatch) -> None:
    call_log_id, summary_id, message_id = _call_log_with_summary()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        call_log = db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).first()
        assert user is not None and call_log is not None
        monkeypatch.setattr(settings, "make_elevenlabs_webhook_url", "https://example.com/webhook", raising=False)
        monkeypatch.setattr(settings, "mail_call_provider", "make", raising=False)

        captured: dict[str, object] = {}

        class _Response:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

        def _post(url: str, json: dict[str, object], timeout: float):
            captured["url"] = url
            captured["json"] = json
            captured["timeout"] = timeout
            return _Response()

        monkeypatch.setattr(httpx, "post", _post)

        result = send_mail_summary_call_to_make(db, user, call_log)
        assert result["success"] is True
        assert result["provider"] == "make"
        assert captured["url"] == "https://example.com/webhook"
        payload = captured["json"]
        assert set(payload.keys()) == {"user_name", "preferred_language", "call_purpose", "total_emails", "mail_call_id", "call_id", "emails_json"}
        assert payload["call_purpose"] == "daily_mail_summary"
        assert payload["total_emails"] == 1
        assert payload["mail_call_id"] == call_log_id
        assert payload["call_id"] == call_log_id
        emails = json.loads(payload["emails_json"])
        assert len(emails) == 1
        assert emails[0]["sender_name"] == "Portfolio Contact Form"
        assert emails[0]["subject"] == "Portfolio inquiry"
        assert "notify+abc@example.com" not in payload["emails_json"]
        assert "Forwarded message" not in payload["emails_json"]
        assert "raw body" not in payload["emails_json"].lower()
        assert "http://" not in payload["emails_json"].lower()
    finally:
        db.close()
        _cleanup(call_log_id, summary_id, message_id)


def test_payload_preserves_summary_order_for_voice_selection(monkeypatch) -> None:
    call_log_id, summary_id, message_id = _call_log_with_summary()
    db = SessionLocal()
    extra_message_ids: list[int] = []
    extra_summary_ids: list[int] = []
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        call_log = db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).first()
        assert user is not None and call_log is not None

        for index in range(2, 4):
            message = EmailMessage(
                user_id=user.id,
                gmail_message_id=f"make-order-test-{uuid4()}",
                gmail_thread_id=None,
                sender=f"sender{index}@example.com",
                recipient=user.email,
                subject=f"Order Test Email {index}",
                snippet=f"Snippet {index}",
                plain_body=f"Body {index}",
                html_body=None,
                received_at=datetime.now(timezone.utc),
                has_attachments=False,
                attachment_metadata=None,
                is_read_from_gmail=True,
                is_summarized=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(message)
            db.flush()
            extra_message_ids.append(message.id)
            summary = EmailSummary(
                user_id=user.id,
                email_message_id=message.id,
                sender=message.sender,
                subject=message.subject,
                short_summary=f"Short summary {index}",
                detailed_summary=f"Detailed summary {index}",
                action_required_text=None,
                attachment_note=None,
                summary_status="completed",
                error_message=None,
                is_delivered_in_mail_call=False,
                delivered_at=None,
                mail_call_log_id=None,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(summary)
            db.flush()
            extra_summary_ids.append(summary.id)

        custom_order = [extra_summary_ids[1], summary_id, extra_summary_ids[0]]
        call_log.delivered_summary_ids = json.dumps(custom_order)
        call_log.summary_count = len(custom_order)
        db.add(call_log)
        db.commit()

        monkeypatch.setattr(settings, "make_elevenlabs_webhook_url", "https://example.com/webhook", raising=False)

        captured: dict[str, object] = {}

        class _Response:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

        def _post(url: str, json: dict[str, object], timeout: float):
            captured["json"] = json
            return _Response()

        monkeypatch.setattr(httpx, "post", _post)

        result = send_mail_summary_call_to_make(db, user, call_log)
        assert result["success"] is True
        emails = json.loads(captured["json"]["emails_json"])
        assert [item["number"] for item in emails] == [1, 2, 3]
        assert emails[0]["subject"] == "Order Test Email 3"
        assert emails[1]["subject"] == "Portfolio inquiry"
        assert emails[2]["subject"] == "Order Test Email 2"
    finally:
        db.close()
        db = SessionLocal()
        try:
            db.query(EmailSummary).filter(EmailSummary.id.in_(extra_summary_ids)).delete(synchronize_session=False)
            db.query(EmailMessage).filter(EmailMessage.id.in_(extra_message_ids)).delete(synchronize_session=False)
            db.commit()
        finally:
            db.close()
        _cleanup(call_log_id, summary_id, message_id)


def test_missing_webhook_url_returns_safe_failure(monkeypatch) -> None:
    call_log_id, summary_id, message_id = _call_log_with_summary()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        call_log = db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).first()
        assert user is not None and call_log is not None
        monkeypatch.setattr(settings, "make_elevenlabs_webhook_url", "", raising=False)

        result = send_mail_summary_call_to_make(db, user, call_log)
        assert result["success"] is False
        assert result["status"] == "missing_config"
        assert "not configured" in result["message"].lower()
    finally:
        db.close()
        _cleanup(call_log_id, summary_id, message_id)


def test_successful_make_post(monkeypatch) -> None:
    call_log_id, summary_id, message_id = _call_log_with_summary()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        call_log = db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).first()
        assert user is not None and call_log is not None
        monkeypatch.setattr(settings, "make_elevenlabs_webhook_url", "https://example.com/webhook", raising=False)

        class _Response:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

        monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: _Response())
        result = send_mail_summary_call_to_make(db, user, call_log)
        assert result["success"] is True
        assert result["status"] == "queued"
        assert result["payload"]["mail_call_id"] == call_log_id
    finally:
        db.close()
        _cleanup(call_log_id, summary_id, message_id)


def test_make_failure_falls_back_safely(monkeypatch) -> None:
    call_log_id, summary_id, message_id = _call_log_with_summary()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        call_log = db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).first()
        assert user is not None and call_log is not None
        monkeypatch.setattr(settings, "make_elevenlabs_webhook_url", "https://example.com/webhook", raising=False)

        class _Response:
            status_code = 500

            def raise_for_status(self) -> None:
                raise httpx.HTTPStatusError("bad", request=httpx.Request("POST", "https://example.com/webhook"), response=httpx.Response(500))

        monkeypatch.setattr(httpx, "post", lambda *args, **kwargs: _Response())
        result = send_mail_summary_call_to_make(db, user, call_log)
        assert result["success"] is False
        assert result["status"] == "failed"
        assert "could not be sent" in result["message"].lower()
        assert result["payload"]["mail_call_id"] == call_log_id
    finally:
        db.close()
        _cleanup(call_log_id, summary_id, message_id)


def test_no_raw_body_or_full_email_addresses_in_emails_json(monkeypatch) -> None:
    call_log_id, summary_id, message_id = _call_log_with_summary()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        call_log = db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).first()
        assert user is not None and call_log is not None
        monkeypatch.setattr(settings, "make_elevenlabs_webhook_url", "https://example.com/webhook", raising=False)

        captured: dict[str, object] = {}

        class _Response:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

        def _post(url: str, json: dict[str, object], timeout: float):
            captured["json"] = json
            return _Response()

        monkeypatch.setattr(httpx, "post", _post)
        result = send_mail_summary_call_to_make(db, user, call_log)
        assert result["success"] is True
        emails_json = captured["json"]["emails_json"]
        assert captured["json"]["mail_call_id"] == call_log_id
        assert "Portfolio Contact Form <notify+abc@example.com>" not in emails_json
        assert "notify+abc@example.com" not in emails_json
        assert "Forwarded message" not in emails_json
        assert "please review the attached portfolio" not in emails_json.lower()
    finally:
        db.close()
        _cleanup(call_log_id, summary_id, message_id)
