from __future__ import annotations

import json
from datetime import date, datetime, time, timezone, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.database.session import SessionLocal
from app.main import app
from app.models.email_message import EmailMessage
from app.models.email_summary import EmailSummary
from app.models.email_reply_action import EmailReplyAction
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.recurring_reminder_rule import RecurringReminderRule
from app.models.user import User
from app.models.voice_call_interaction import VoiceCallInteraction
from app.models.voice_reminder_session import VoiceReminderSession
from app.models.voice_reply_session import VoiceReplySession
from app.services import voice_call_service


client = TestClient(app)
AGENT_KEY = "test-agent-tool-secret"


def _login_token() -> str:
    response = client.post(
        "/auth/login",
        json={"email": "browsertest@example.com", "password": "Test@12345"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _set_agent_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "agent_tool_api_key", AGENT_KEY, raising=False)


def _create_voice_test_call() -> tuple[int, list[int], list[int]]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        assert user is not None

        message_ids: list[int] = []
        summary_ids: list[int] = []
        for index in range(1, 4):
            message = EmailMessage(
                user_id=user.id,
                gmail_message_id=f"phase9-test-{uuid4()}",
                gmail_thread_id=None,
                sender=f"sender{index}@example.com",
                recipient=user.email,
                subject=f"Phase 9 Test Email {index}",
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
            message_ids.append(message.id)
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
            summary_ids.append(summary.id)

        call_log = MailSummaryCallLog(
            user_id=user.id,
            call_type="mail_summary",
            call_status="prepared",
            call_date=date.today(),
            call_time=time(9, 0),
            summary_count=len(summary_ids),
            script_text="Test script",
            delivery_status="pending",
            delivered_summary_ids=json.dumps(summary_ids),
            failure_reason=None,
            provider="twilio",
            provider_call_id=f"CA-test-phase9-{uuid4()}",
            to_phone_number=user.phone_number,
            from_phone_number="+17154196839",
            call_started_at=None,
            call_completed_at=None,
            call_duration_seconds=None,
            provider_status="in-progress",
            provider_error_message=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(call_log)
        db.commit()
        db.refresh(call_log)
        return call_log.id, summary_ids, message_ids
    finally:
        db.close()


def _cleanup_voice_test_call(call_log_id: int, summary_ids: list[int], message_ids: list[int]) -> None:
    db = SessionLocal()
    try:
        session_ids = [
            row[0]
            for row in db.query(VoiceReminderSession.created_recurring_rule_id)
            .filter(
                VoiceReminderSession.mail_call_log_id == call_log_id,
                VoiceReminderSession.created_recurring_rule_id.is_not(None),
            )
            .all()
        ]
        db.query(VoiceCallInteraction).filter(VoiceCallInteraction.mail_call_log_id == call_log_id).delete(synchronize_session=False)
        db.query(EmailReplyAction).filter(EmailReplyAction.mail_call_log_id == call_log_id).delete(synchronize_session=False)
        db.query(VoiceReplySession).filter(VoiceReplySession.mail_call_log_id == call_log_id).delete(synchronize_session=False)
        db.query(VoiceReminderSession).filter(VoiceReminderSession.mail_call_log_id == call_log_id).delete(synchronize_session=False)
        db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).delete(synchronize_session=False)
        db.query(EmailSummary).filter(EmailSummary.id.in_(summary_ids)).delete(synchronize_session=False)
        db.query(EmailMessage).filter(EmailMessage.id.in_(message_ids)).delete(synchronize_session=False)
        if session_ids:
            db.query(RecurringReminderRule).filter(RecurringReminderRule.id.in_(session_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_twilio_speech_webhook_handles_phase9_intents() -> None:
    token = _login_token()
    call_log_id, summary_ids, message_ids = _create_voice_test_call()
    try:
        headers = {"Authorization": f"Bearer {token}"}
        db = SessionLocal()
        try:
            provider_call_id = db.query(MailSummaryCallLog.provider_call_id).filter(MailSummaryCallLog.id == call_log_id).scalar()
        finally:
            db.close()

        detail_response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "Tell me more about the first email", "Confidence": "0.92", "CallSid": provider_call_id},
        )
        assert detail_response.status_code == 200
        assert "Gather" in detail_response.text
        assert "Do you want another email explained" in detail_response.text

        interactions = client.get(f"/voice/mail-calls/{call_log_id}/interactions", headers=headers)
        assert interactions.status_code == 200, interactions.text
        first_payload = interactions.json()
        assert first_payload[0]["detected_intent"] == "DETAIL_EMAIL"
        assert first_payload[0]["email_reference"] == 1

        help_response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "What can I say?", "Confidence": "0.95", "CallSid": provider_call_id},
        )
        assert help_response.status_code == 200
        assert "Gather" in help_response.text

        repeat_response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "Repeat that", "Confidence": "0.92", "CallSid": provider_call_id},
        )
        assert repeat_response.status_code == 200
        assert "Gather" in repeat_response.text

        know_response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "I want to know more", "Confidence": "0.92", "CallSid": provider_call_id},
        )
        assert know_response.status_code == 200
        assert "Sorry, I did not understand" in know_response.text or "Gather" in know_response.text

        end_response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "no", "Confidence": "0.92", "CallSid": provider_call_id},
        )
        assert end_response.status_code == 200
        assert "Ending the call" in end_response.text or "ending the call" in end_response.text.lower()
        assert "hangup" in end_response.text.lower()

        interactions = client.get(f"/voice/mail-calls/{call_log_id}/interactions", headers=headers)
        assert interactions.status_code == 200, interactions.text
        payload = interactions.json()
        assert len(payload) >= 4
        assert any(item["detected_intent"] == "DETAIL_EMAIL" for item in payload)
        assert any(item["detected_intent"] == "HELP" for item in payload)
        assert any(item["detected_intent"] == "REPEAT_SUMMARY" for item in payload)
        assert any(item["detected_intent"] == "END_CALL" for item in payload)
    finally:
        _cleanup_voice_test_call(call_log_id, summary_ids, message_ids)


def test_twilio_detail_phrases_map_to_first_email() -> None:
    token = _login_token()
    try:
        phrases = [
            "explain in detail email number 1",
            "explain email number one",
            "tell me details about first email",
            "details of email 1",
            "read detailed summary for first email",
        ]
        for phrase in phrases:
            call_log_id, summary_ids, message_ids = _create_voice_test_call()
            headers = {"Authorization": f"Bearer {token}"}
            db = SessionLocal()
            try:
                provider_call_id = db.query(MailSummaryCallLog.provider_call_id).filter(MailSummaryCallLog.id == call_log_id).scalar()
            finally:
                db.close()
            response = client.post(
                f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
                data={"SpeechResult": phrase, "Confidence": "0.94", "CallSid": provider_call_id},
            )
            assert response.status_code == 200, response.text
            assert "Gather" in response.text
            assert "Do you want another email explained" in response.text

            interactions = client.get(f"/voice/mail-calls/{call_log_id}/interactions", headers=headers)
            assert interactions.status_code == 200, interactions.text
            payload = interactions.json()
            assert any(item["detected_intent"] == "DETAIL_EMAIL" and item["email_reference"] == 1 for item in payload)
            _cleanup_voice_test_call(call_log_id, summary_ids, message_ids)
    finally:
        pass


def test_twilio_speech_webhook_handles_phase10_lookup_phrases() -> None:
    token = _login_token()
    call_log_id, summary_ids, message_ids = _create_voice_test_call()
    try:
        headers = {"Authorization": f"Bearer {token}"}
        db = SessionLocal()
        try:
            provider_call_id = db.query(MailSummaryCallLog.provider_call_id).filter(MailSummaryCallLog.id == call_log_id).scalar()
        finally:
            db.close()

        sender_response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "Read the email from Google", "Confidence": "0.92", "CallSid": provider_call_id},
        )
        assert sender_response.status_code == 200
        assert "Gather" in sender_response.text

        subject_response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "Tell me about the Kaggle notebook email", "Confidence": "0.92", "CallSid": provider_call_id},
        )
        assert subject_response.status_code == 200
        assert "Gather" in subject_response.text

        latest_response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "Explain the latest email", "Confidence": "0.92", "CallSid": provider_call_id},
        )
        assert latest_response.status_code == 200
        assert "Gather" in latest_response.text

        interactions = client.get(f"/voice/mail-calls/{call_log_id}/interactions", headers=headers)
        assert interactions.status_code == 200, interactions.text
        payload = interactions.json()
        assert len(payload) >= 3
        assert any(item["detected_intent"] == "DETAIL_EMAIL" for item in payload)
    finally:
        _cleanup_voice_test_call(call_log_id, summary_ids, message_ids)


def test_twilio_detail_phrase_invalid_reference_returns_helpful_message() -> None:
    token = _login_token()
    call_log_id, summary_ids, message_ids = _create_voice_test_call()
    try:
        headers = {"Authorization": f"Bearer {token}"}
        db = SessionLocal()
        try:
            provider_call_id = db.query(MailSummaryCallLog.provider_call_id).filter(MailSummaryCallLog.id == call_log_id).scalar()
        finally:
            db.close()

        response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "explain email number 9", "Confidence": "0.94", "CallSid": provider_call_id},
        )
        assert response.status_code == 200, response.text
        assert "Email number not found" in response.text or "between one and five" in response.text
        assert "application error" not in response.text.lower()

        interactions = client.get(f"/voice/mail-calls/{call_log_id}/interactions", headers=headers)
        assert interactions.status_code == 200, interactions.text
        payload = interactions.json()
        assert any(item["detected_intent"] == "UNKNOWN" for item in payload)
    finally:
        _cleanup_voice_test_call(call_log_id, summary_ids, message_ids)


def test_twilio_speech_webhook_uses_safe_detail_fallback_when_detailed_summary_missing() -> None:
    token = _login_token()
    call_log_id, summary_ids, message_ids = _create_voice_test_call()
    db = SessionLocal()
    try:
        summary = db.query(EmailSummary).filter(EmailSummary.id == summary_ids[0]).first()
        assert summary is not None
        summary.detailed_summary = None
        summary.short_summary = "This reminder mail needs review."
        summary.action_required_text = "No clear action requested."
        db.add(summary)
        db.commit()

        headers = {"Authorization": f"Bearer {token}"}
        provider_call_id = db.query(MailSummaryCallLog.provider_call_id).filter(MailSummaryCallLog.id == call_log_id).scalar()
        assert provider_call_id
        response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "explain email number 1", "Confidence": "0.95", "CallSid": provider_call_id},
        )
        assert response.status_code == 200, response.text
        assert "Gather" in response.text
        assert "Detailed explanation is not available" in response.text or "This reminder mail needs review" in response.text

        interactions = client.get(f"/voice/mail-calls/{call_log_id}/interactions", headers=headers)
        assert interactions.status_code == 200, interactions.text
        payload = interactions.json()
        assert any(item["detected_intent"] == "DETAIL_EMAIL" for item in payload)
    finally:
        db.close()
        _cleanup_voice_test_call(call_log_id, summary_ids, message_ids)


def test_twilio_detail_response_sanitizes_forwarded_raw_content() -> None:
    token = _login_token()
    call_log_id, summary_ids, message_ids = _create_voice_test_call()
    db = SessionLocal()
    try:
        summary = db.query(EmailSummary).filter(EmailSummary.id == summary_ids[0]).first()
        assert summary is not None
        summary.detailed_summary = (
            "---------- Forwarded message ---------\n"
            "From: Portfolio Contact Form <notify+abc@example.com>\n"
            "Date: Tue, 12 Jun 2026 10:00 AM\n"
            "Subject: Portfolio inquiry\n"
            "To: user@example.com\n\n"
            "Please review the attached portfolio and reply if needed."
        )
        summary.short_summary = "Portfolio inquiry mail needs review."
        summary.action_required_text = "Please review and respond."
        db.add(summary)
        db.commit()

        headers = {"Authorization": f"Bearer {token}"}
        provider_call_id = db.query(MailSummaryCallLog.provider_call_id).filter(MailSummaryCallLog.id == call_log_id).scalar()
        assert provider_call_id

        response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "Explain the email number one", "Confidence": "0.95", "CallSid": provider_call_id},
        )
        assert response.status_code == 200, response.text
        assert "Gather" in response.text
        assert "Forwarded message" not in response.text
        assert "notify+abc@example.com" not in response.text
        assert "----------" not in response.text
        assert "Portfolio inquiry" in response.text or "needs review" in response.text

        interactions = client.get(f"/voice/mail-calls/{call_log_id}/interactions", headers=headers)
        assert interactions.status_code == 200, interactions.text
        payload = interactions.json()
        assert any(item["detected_intent"] == "DETAIL_EMAIL" for item in payload)
    finally:
        db.close()
        _cleanup_voice_test_call(call_log_id, summary_ids, message_ids)


def test_twilio_speech_webhook_handles_phase11_reply_flow(monkeypatch) -> None:
    token = _login_token()
    call_log_id, summary_ids, message_ids = _create_voice_test_call()
    try:
        headers = {"Authorization": f"Bearer {token}"}
        db = SessionLocal()
        try:
            provider_call_id = db.query(MailSummaryCallLog.provider_call_id).filter(MailSummaryCallLog.id == call_log_id).scalar()
        finally:
            db.close()

        monkeypatch.setattr(voice_call_service, "send_reply", lambda *args, **kwargs: {"provider_message_id": "msg-123"})

        start_response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "reply to email number one", "Confidence": "0.92", "CallSid": provider_call_id},
        )
        assert start_response.status_code == 200
        assert "What would you like me to say?" in start_response.text

        db = SessionLocal()
        try:
            session = db.query(VoiceReplySession).filter(VoiceReplySession.mail_call_log_id == call_log_id).first()
            assert session is not None
            assert session.status == "awaiting_body"
        finally:
            db.close()

        body_response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "tell them I will join the meeting", "Confidence": "0.92", "CallSid": provider_call_id},
        )
        assert body_response.status_code == 200
        assert "Should I send this reply?" in body_response.text

        confirm_response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "yes send it", "Confidence": "0.92", "CallSid": provider_call_id},
        )
        assert confirm_response.status_code == 200
        assert "hangup" in confirm_response.text.lower()

        interactions = client.get(f"/voice/mail-calls/{call_log_id}/interactions", headers=headers)
        assert interactions.status_code == 200, interactions.text
        payload = interactions.json()
        assert any(item["detected_intent"] == "START_EMAIL_REPLY" for item in payload)
        assert any(item["detected_intent"] == "CAPTURE_REPLY_BODY" for item in payload)
        assert any(item["detected_intent"] == "CONFIRM_SEND_REPLY" for item in payload)
    finally:
        _cleanup_voice_test_call(call_log_id, summary_ids, message_ids)


def test_voice_mail_call_reply_requires_confirmation(monkeypatch) -> None:
    _set_agent_key(monkeypatch)
    call_log_id, summary_ids, message_ids = _create_voice_test_call()
    try:
        def _should_not_send(*args, **kwargs):  # pragma: no cover - safety guard
            raise AssertionError("send_reply should not be called before confirmation")

        monkeypatch.setattr(voice_call_service, "send_reply", _should_not_send)

        response = client.post(
            f"/voice/mail-calls/{call_log_id}/reply",
            headers={"X-Agent-API-Key": AGENT_KEY},
            json={"email_number": 1, "reply_text": "Thanks, I will review this.", "confirmed": False},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is False
        assert payload["status"] == "confirmation_required"
        assert "confirm" in payload["message"].lower()
    finally:
        _cleanup_voice_test_call(call_log_id, summary_ids, message_ids)


def test_voice_mail_call_reply_sends_when_confirmed(monkeypatch) -> None:
    _set_agent_key(monkeypatch)
    call_log_id, summary_ids, message_ids = _create_voice_test_call()
    captured: dict[str, object] = {}
    try:
        def _fake_send_reply(db, user, session):
            captured["user_id"] = user.id
            captured["session"] = session
            return {"provider_message_id": "mock-provider-message-id"}

        monkeypatch.setattr(voice_call_service, "send_reply", _fake_send_reply)

        response = client.post(
            f"/voice/mail-calls/{call_log_id}/reply",
            headers={"X-Agent-API-Key": AGENT_KEY},
            json={"email_number": 1, "reply_text": "Thanks, I will review this.", "confirmed": True},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is True
        assert payload["status"] == "sent"
        assert payload["data"]["email_number"] == 1
        session = captured.get("session")
        assert session is not None
        assert session.reply_body == "Thanks, I will review this."
        assert session.target_email_reference == 1
    finally:
        _cleanup_voice_test_call(call_log_id, summary_ids, message_ids)


def test_voice_mail_call_reply_invalid_email_number_fails_safely(monkeypatch) -> None:
    _set_agent_key(monkeypatch)
    call_log_id, summary_ids, message_ids = _create_voice_test_call()
    try:
        called = {"value": False}

        def _should_not_send(*args, **kwargs):  # pragma: no cover - safety guard
            called["value"] = True
            raise AssertionError("send_reply should not be called for an invalid email number")

        monkeypatch.setattr(voice_call_service, "send_reply", _should_not_send)

        response = client.post(
            f"/voice/mail-calls/{call_log_id}/reply",
            headers={"X-Agent-API-Key": AGENT_KEY},
            json={"email_number": 99, "reply_text": "Thanks, I will review this.", "confirmed": True},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is False
        assert payload["status"] == "invalid_email_number"
        assert "could not find" in payload["message"].lower()
        assert called["value"] is False
    finally:
        _cleanup_voice_test_call(call_log_id, summary_ids, message_ids)


def test_voice_mail_call_reply_empty_text_fails_safely(monkeypatch) -> None:
    _set_agent_key(monkeypatch)
    call_log_id, summary_ids, message_ids = _create_voice_test_call()
    try:
        called = {"value": False}

        def _should_not_send(*args, **kwargs):  # pragma: no cover - safety guard
            called["value"] = True
            raise AssertionError("send_reply should not be called for an empty reply")

        monkeypatch.setattr(voice_call_service, "send_reply", _should_not_send)

        response = client.post(
            f"/voice/mail-calls/{call_log_id}/reply",
            headers={"X-Agent-API-Key": AGENT_KEY},
            json={"email_number": 1, "reply_text": "   ", "confirmed": True},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["success"] is False
        assert payload["status"] == "invalid_reply_text"
        assert "reply should say" in payload["message"].lower()
        assert called["value"] is False
    finally:
        _cleanup_voice_test_call(call_log_id, summary_ids, message_ids)


def test_voice_mail_call_reply_requires_agent_key(monkeypatch) -> None:
    _set_agent_key(monkeypatch)
    call_log_id, summary_ids, message_ids = _create_voice_test_call()
    try:
        response = client.post(
            f"/voice/mail-calls/{call_log_id}/reply",
            json={"email_number": 1, "reply_text": "Thanks, I will review this.", "confirmed": True},
        )
        assert response.status_code == 401, response.text
    finally:
        _cleanup_voice_test_call(call_log_id, summary_ids, message_ids)


def test_twilio_speech_webhook_handles_recurring_reminder_flow() -> None:
    token = _login_token()
    call_log_id, summary_ids, message_ids = _create_voice_test_call()
    try:
        headers = {"Authorization": f"Bearer {token}"}
        db = SessionLocal()
        try:
            provider_call_id = db.query(MailSummaryCallLog.provider_call_id).filter(MailSummaryCallLog.id == call_log_id).scalar()
        finally:
            db.close()

        recurring_response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "Remind me every day at 8 pm", "Confidence": "0.92", "CallSid": provider_call_id},
        )
        assert recurring_response.status_code == 200, recurring_response.text
        assert "save it" in recurring_response.text.lower()

        db = SessionLocal()
        try:
            session = db.query(VoiceReminderSession).filter(VoiceReminderSession.mail_call_log_id == call_log_id).first()
            assert session is not None
            assert session.repeat_type == "daily"
            assert session.status == "awaiting_confirmation"
            assert session.time_of_day == "20:00"
        finally:
            db.close()

        confirm_response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "yes save it", "Confidence": "0.92", "CallSid": provider_call_id},
        )
        assert confirm_response.status_code == 200, confirm_response.text
        assert "created" in confirm_response.text.lower()

        db = SessionLocal()
        try:
            session = db.query(VoiceReminderSession).filter(VoiceReminderSession.mail_call_log_id == call_log_id).first()
            assert session is not None
            assert session.created_recurring_rule_id is not None
            rule = db.query(RecurringReminderRule).filter(RecurringReminderRule.id == session.created_recurring_rule_id).first()
            assert rule is not None
            assert rule.repeat_type == "daily"
            assert rule.time_of_day == "20:00"
        finally:
            db.close()

        interactions = client.get(f"/voice/mail-calls/{call_log_id}/interactions", headers=headers)
        assert interactions.status_code == 200, interactions.text
        payload = interactions.json()
        assert any(item["detected_intent"] == "CREATE_RECURRING_REMINDER" for item in payload)
        assert any(item["detected_intent"] == "CONFIRM_CREATE_REMINDER" for item in payload)
    finally:
        _cleanup_voice_test_call(call_log_id, summary_ids, message_ids)


def test_twilio_speech_webhook_rejects_past_reminder_before_confirmation(monkeypatch) -> None:
    token = _login_token()
    call_log_id, summary_ids, message_ids = _create_voice_test_call()
    try:
        headers = {"Authorization": f"Bearer {token}"}
        db = SessionLocal()
        try:
            provider_call_id = db.query(MailSummaryCallLog.provider_call_id).filter(MailSummaryCallLog.id == call_log_id).scalar()
        finally:
            db.close()

        monkeypatch.setattr(
            voice_call_service,
            "parse_reminder_datetime",
            lambda *args, **kwargs: datetime.now(timezone.utc) - timedelta(minutes=5),
        )

        response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "Remind me about this email in 2 minutes", "Confidence": "0.92", "CallSid": provider_call_id},
        )
        assert response.status_code == 200, response.text
        assert "future time" in response.text.lower()

        db = SessionLocal()
        try:
            session = db.query(VoiceReminderSession).filter(VoiceReminderSession.mail_call_log_id == call_log_id).first()
            assert session is None
        finally:
            db.close()

        interactions = client.get(f"/voice/mail-calls/{call_log_id}/interactions", headers=headers)
        assert interactions.status_code == 200, interactions.text
        payload = interactions.json()
        assert any(item["detected_intent"] == "START_REMINDER_CREATE" or item["detected_intent"] == "CAPTURE_REMINDER_DATETIME" for item in payload)
    finally:
        monkeypatch.undo()
        _cleanup_voice_test_call(call_log_id, summary_ids, message_ids)


def test_twilio_speech_webhook_uses_last_explained_email_for_this_email_reminder() -> None:
    token = _login_token()
    call_log_id, summary_ids, message_ids = _create_voice_test_call()
    try:
        headers = {"Authorization": f"Bearer {token}"}
        db = SessionLocal()
        try:
            provider_call_id = db.query(MailSummaryCallLog.provider_call_id).filter(MailSummaryCallLog.id == call_log_id).scalar()
        finally:
            db.close()

        detail_response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "Explain email number one", "Confidence": "0.92", "CallSid": provider_call_id},
        )
        assert detail_response.status_code == 200, detail_response.text
        assert "Gather" in detail_response.text

        reminder_response = client.post(
            f"/voice/webhooks/twilio/speech?call_log_id={call_log_id}",
            data={"SpeechResult": "Remind me about this email in 5 minutes", "Confidence": "0.92", "CallSid": provider_call_id},
        )
        assert reminder_response.status_code == 200, reminder_response.text
        assert "save it" in reminder_response.text.lower()

        db = SessionLocal()
        try:
            session = db.query(VoiceReminderSession).filter(VoiceReminderSession.mail_call_log_id == call_log_id).first()
            assert session is not None
            assert session.email_summary_id == summary_ids[0]
            assert session.target_email_reference == 1
            assert session.status == "awaiting_confirmation"
            assert session.reminder_at is not None
            assert session.reminder_at > datetime.now(timezone.utc)
        finally:
            db.close()

        interactions = client.get(f"/voice/mail-calls/{call_log_id}/interactions", headers=headers)
        assert interactions.status_code == 200, interactions.text
        payload = interactions.json()
        assert any(item["detected_intent"] == "DETAIL_EMAIL" and item["email_reference"] == 1 for item in payload)
        assert any(item["detected_intent"] == "START_REMINDER_CREATE" for item in payload)
    finally:
        _cleanup_voice_test_call(call_log_id, summary_ids, message_ids)
