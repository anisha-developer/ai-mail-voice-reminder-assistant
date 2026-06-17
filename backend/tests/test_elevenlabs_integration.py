from __future__ import annotations

import json
from datetime import datetime, time, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.database.session import SessionLocal
from app.main import app
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.user import User
from app.models.voice_call_interaction import VoiceCallInteraction
from app.schemas.agent_tools import AgentElevenLabsPostCallRequest, AgentToolRequest
from app.services import voice_call_service

client = TestClient(app)


def _user() -> User:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        assert user is not None
        return user
    finally:
        db.close()


def _prepared_call(user: User) -> tuple[int, str]:
    script_text = f"Test script {uuid4()}"
    db = SessionLocal()
    try:
        call_log = MailSummaryCallLog(
            user_id=user.id,
            call_type="mail_summary",
            call_status="prepared",
            call_date=datetime.now(timezone.utc).date(),
            call_time=time(9, 0),
            summary_count=1,
            script_text=script_text,
            delivery_status="pending",
            delivered_summary_ids=json.dumps([1]),
            provider=None,
            provider_call_id=None,
            to_phone_number=user.phone_number,
            from_phone_number=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(call_log)
        db.commit()
        db.refresh(call_log)
        return call_log.id, script_text
    finally:
        db.close()


def test_agent_tool_request_coerces_strings_and_empty_values() -> None:
    payload = AgentToolRequest(
        action="create_recurring_reminder",
        user_id="123",
        call_id="456",
        email_reference="7",
        email_summary_id="8",
        email_message_id="9",
        query="   ",
        title="Reminder",
        notes="",
        reminder_time_text="tomorrow",
        reminder_at="",
        repeat_type="weekly",
        interval_value="2",
        interval_unit="weeks",
        time_of_day="09:00",
        days_of_week="Mon, Wed , Fri",
        day_of_month="12",
        reply_instruction="",
        draft_id="55",
        timezone="Asia/Kolkata",
        transcript="",
        action_summary="",
        feedback_text="",
    )
    assert payload.user_id == 123
    assert payload.call_id == "456"
    assert payload.email_reference == 7
    assert payload.email_summary_id == 8
    assert payload.email_message_id == 9
    assert payload.query is None
    assert payload.notes is None
    assert payload.reminder_at is None
    assert payload.interval_value == 2
    assert payload.days_of_week == ["Mon", "Wed", "Fri"]
    assert payload.day_of_month == 12
    assert payload.reply_instruction is None
    assert payload.draft_id == 55
    assert payload.transcript is None
    assert payload.action_summary is None
    assert payload.feedback_text is None


def test_elevenlabs_provider_switch_uses_elevenlabs(monkeypatch) -> None:
    user = _user()
    call_log_id, script_text = _prepared_call(user)
    db = SessionLocal()
    try:
        monkeypatch.setattr(settings, "mail_call_provider", "make_elevenlabs", raising=False)
        monkeypatch.setattr(voice_call_service, "send_mail_summary_call_to_make", lambda _db, _user, call_log, summaries=None: {"success": True, "provider": "make", "status": "queued", "message": "ok", "payload": {}})

        result = voice_call_service.start_mail_summary_voice_call(db, user, call_log_id)
        assert result["provider"] == "make_elevenlabs"
        assert result["provider_call_id"] == f"make-elevenlabs-{call_log_id}"
        refreshed = db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).first()
        assert refreshed is not None
        assert refreshed.provider == "make_elevenlabs"
        assert refreshed.call_status == "queued"
    finally:
        db.query(VoiceCallInteraction).filter(VoiceCallInteraction.mail_call_log_id == call_log_id).delete(synchronize_session=False)
        db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_elevenlabs_provider_falls_back_to_twilio_when_unavailable(monkeypatch) -> None:
    user = _user()
    call_log_id, script_text = _prepared_call(user)
    db = SessionLocal()
    try:
        monkeypatch.setattr(settings, "mail_call_provider", "twilio", raising=False)
        monkeypatch.setattr(settings, "twilio_account_sid", "AC123", raising=False)
        monkeypatch.setattr(settings, "twilio_auth_token", "token", raising=False)
        monkeypatch.setattr(settings, "twilio_from_phone", "+17154196839", raising=False)
        monkeypatch.setattr(settings, "public_backend_url", "http://localhost:8000", raising=False)
        class _CallStub:
            sid = "CA-test-sid"
            status = "queued"

        class _CallsStub:
            @staticmethod
            def create(**_kwargs):
                return _CallStub()

        class _ClientStub:
            def __init__(self, *_args, **_kwargs):
                self.calls = _CallsStub()

        monkeypatch.setattr(voice_call_service, "Client", _ClientStub)

        result = voice_call_service.start_mail_summary_voice_call(db, user, call_log_id)
        assert result["provider"] == "twilio"
        assert result["provider_call_id"] == "CA-test-sid"
    finally:
        db.query(VoiceCallInteraction).filter(VoiceCallInteraction.mail_call_log_id == call_log_id).delete(synchronize_session=False)
        db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_unknown_provider_falls_back_to_twilio(monkeypatch) -> None:
    user = _user()
    call_log_id, script_text = _prepared_call(user)
    db = SessionLocal()
    try:
        monkeypatch.setattr(settings, "mail_call_provider", "unknown-provider", raising=False)
        monkeypatch.setattr(settings, "twilio_account_sid", "AC123", raising=False)
        monkeypatch.setattr(settings, "twilio_auth_token", "token", raising=False)
        monkeypatch.setattr(settings, "twilio_from_phone", "+17154196839", raising=False)
        monkeypatch.setattr(settings, "public_backend_url", "http://localhost:8000", raising=False)

        class _CallStub:
            sid = "CA-fallback-sid"
            status = "queued"

        class _CallsStub:
            @staticmethod
            def create(**_kwargs):
                return _CallStub()

        class _ClientStub:
            def __init__(self, *_args, **_kwargs):
                self.calls = _CallsStub()

        monkeypatch.setattr(voice_call_service, "Client", _ClientStub)

        result = voice_call_service.start_mail_summary_voice_call(db, user, call_log_id)
        assert result["provider"] == "twilio"
        assert result["provider_call_id"] == "CA-fallback-sid"
    finally:
        db.query(VoiceCallInteraction).filter(VoiceCallInteraction.mail_call_log_id == call_log_id).delete(synchronize_session=False)
        db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_make_provider_failure_does_not_crash(monkeypatch) -> None:
    user = _user()
    call_log_id, script_text = _prepared_call(user)
    db = SessionLocal()
    try:
        monkeypatch.setattr(settings, "mail_call_provider", "make_elevenlabs", raising=False)
        monkeypatch.setattr(voice_call_service, "send_mail_summary_call_to_make", lambda _db, _user, _call_log, summaries=None: {"success": False, "provider": "make", "status": "failed", "message": "Webhook failed", "payload": {}})

        result = voice_call_service.start_mail_summary_voice_call(db, user, call_log_id)
        assert result["provider"] == "make_elevenlabs"
        assert result["call_status"] == "failed"
        assert result["provider_call_id"] is None
        refreshed = db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).first()
        assert refreshed is not None
        assert refreshed.call_status == "failed"
        assert refreshed.delivery_status == "failed"
    finally:
        db.query(VoiceCallInteraction).filter(VoiceCallInteraction.mail_call_log_id == call_log_id).delete(synchronize_session=False)
        db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_agent_post_call_route_stores_interaction(monkeypatch) -> None:
    monkeypatch.setattr(settings, "agent_tool_api_key", "test-agent-tool-secret", raising=False)
    user = _user()
    call_log_id, script_text = _prepared_call(user)
    response = client.post(
        "/agent/elevenlabs/post-call",
        json={
            "call_id": call_log_id,
            "user_id": user.id,
            "provider_call_id": "el-123",
            "transcript": "Thanks for calling",
            "summary_text": "Call finished successfully",
            "action_summary": "Completed",
            "confidence": "0.92",
        },
        headers={"X-Agent-API-Key": "test-agent-tool-secret"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    db = SessionLocal()
    try:
        interaction = (
            db.query(VoiceCallInteraction)
            .filter(VoiceCallInteraction.mail_call_log_id == call_log_id)
            .order_by(VoiceCallInteraction.id.desc())
            .first()
        )
        assert interaction is not None
        assert interaction.detected_intent == "AGENT_POST_CALL"
        assert interaction.provider_call_id == "el-123"
    finally:
        db.query(VoiceCallInteraction).filter(VoiceCallInteraction.mail_call_log_id == call_log_id).delete(synchronize_session=False)
        db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_agent_post_call_route_accepts_string_call_id(monkeypatch) -> None:
    monkeypatch.setattr(settings, "agent_tool_api_key", "test-agent-tool-secret", raising=False)
    response = client.post(
        "/agent/elevenlabs/post-call",
        json={
            "call_id": "elevenlabs-test",
            "user_id": 2,
            "transcript": "User asked for email summaries.",
            "summary_text": "Read summaries and created a reminder.",
            "status": "completed",
        },
        headers={"X-Agent-API-Key": "test-agent-tool-secret"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["stored"] is False


def test_agent_post_call_route_rejects_bad_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "agent_tool_api_key", "test-agent-tool-secret", raising=False)
    response = client.post(
        "/agent/elevenlabs/post-call",
        json={"call_id": 1},
        headers={"X-Agent-API-Key": "wrong"},
    )
    assert response.status_code == 401
