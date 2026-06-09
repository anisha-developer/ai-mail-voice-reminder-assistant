from __future__ import annotations

import json
from datetime import datetime, time, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.config import settings
from app.database.session import SessionLocal
from app.main import app
from app.models.email_message import EmailMessage
from app.models.email_reply_action import EmailReplyAction
from app.models.email_summary import EmailSummary
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.recurring_reminder_rule import RecurringReminderRule
from app.models.reminder import Reminder
from app.models.user import User
from app.models.voice_call_interaction import VoiceCallInteraction
from app.services.agent_tool_service import build_today_summaries_voice_message

client = TestClient(app)

AGENT_KEY = "test-agent-tool-secret"


def _set_agent_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "agent_tool_api_key", AGENT_KEY, raising=False)


def _headers() -> dict[str, str]:
    return {"X-Agent-API-Key": AGENT_KEY}


def _create_user_if_needed() -> User:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        if user is None:
            raise AssertionError("Expected browsertest@example.com to exist")
        return user
    finally:
        db.close()


def _create_agent_fixture() -> tuple[int, int, int]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        assert user is not None
        call_log = MailSummaryCallLog(
            user_id=user.id,
            call_type="mail_summary",
            call_status="delivered",
            call_date=datetime.now(timezone.utc).date(),
            call_time=time(9, 0),
            summary_count=0,
            script_text="Agent tool fixture",
            delivery_status="delivered",
            delivered_summary_ids=json.dumps([]),
            provider="twilio",
            provider_call_id=f"CA-{uuid4()}",
            to_phone_number=user.phone_number,
            from_phone_number="+17154196839",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(call_log)
        db.flush()

        email = EmailMessage(
            user_id=user.id,
            gmail_message_id=f"agent-tool-{uuid4()}",
            gmail_thread_id=f"thread-{uuid4()}",
            sender="mentor@example.com",
            recipient=user.email,
            subject="Project College Update",
            snippet="Please review the college project.",
            plain_body="Please review the college project and reply with your availability.",
            html_body=None,
            received_at=datetime.now(timezone.utc),
            has_attachments=False,
            attachment_metadata=None,
            is_read_from_gmail=True,
            is_summarized=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(email)
        db.flush()

        summary = EmailSummary(
            user_id=user.id,
            email_message_id=email.id,
            sender=email.sender,
            subject=email.subject,
            short_summary="Mentor asked for a college project update.",
            detailed_summary="Mentor asked for a college project update and wants a reply with availability.",
            action_required_text="Reply with your availability.",
            attachment_note="No attachments mentioned.",
            summary_status="completed",
            error_message=None,
            is_delivered_in_mail_call=False,
            delivered_at=None,
            mail_call_log_id=call_log.id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(summary)
        db.flush()
        call_log.summary_count = 1
        call_log.delivered_summary_ids = json.dumps([summary.id])
        call_log.updated_at = datetime.now(timezone.utc)
        db.add(call_log)
        db.commit()
        return user.id, summary.id, call_log.id
    finally:
        db.close()


def _create_agent_fixture_with_summaries(summary_count: int) -> tuple[int, list[int], int]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        assert user is not None
        call_log = MailSummaryCallLog(
            user_id=user.id,
            call_type="mail_summary",
            call_status="delivered",
            call_date=datetime.now(timezone.utc).date(),
            call_time=time(9, 0),
            summary_count=0,
            script_text="Agent tool multi summary fixture",
            delivery_status="delivered",
            delivered_summary_ids=json.dumps([]),
            provider="twilio",
            provider_call_id=f"CA-{uuid4()}",
            to_phone_number=user.phone_number,
            from_phone_number="+17154196839",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(call_log)
        db.flush()

        summary_ids: list[int] = []
        for index in range(1, summary_count + 1):
            email = EmailMessage(
                user_id=user.id,
                gmail_message_id=f"agent-tool-multi-{index}-{uuid4()}",
                gmail_thread_id=f"thread-{uuid4()}",
                sender=f"sender{index}@example.com",
                recipient=user.email,
                subject=f"Subject {index}",
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
            db.add(email)
            db.flush()

            summary = EmailSummary(
                user_id=user.id,
                email_message_id=email.id,
                sender=email.sender,
                subject=email.subject,
                short_summary=f"Short summary {index}",
                detailed_summary=f"Detailed summary {index}",
                action_required_text=None,
                attachment_note=None,
                summary_status="completed",
                error_message=None,
                is_delivered_in_mail_call=False,
                delivered_at=None,
                mail_call_log_id=call_log.id,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db.add(summary)
            db.flush()
            summary_ids.append(summary.id)

        call_log.summary_count = len(summary_ids)
        call_log.delivered_summary_ids = json.dumps(summary_ids)
        call_log.updated_at = datetime.now(timezone.utc)
        db.add(call_log)
        db.commit()
        return user.id, summary_ids, call_log.id
    finally:
        db.close()


def test_missing_api_key_returns_401() -> None:
    settings.agent_tool_api_key = AGENT_KEY
    response = client.post("/agent/tools", json={"action": "get_today_summaries", "user_id": 1})
    assert response.status_code == 401


def test_wrong_api_key_returns_401(monkeypatch) -> None:
    _set_agent_key(monkeypatch)
    response = client.post("/agent/tools", json={"action": "get_today_summaries", "user_id": 1}, headers={"X-Agent-API-Key": "wrong"})
    assert response.status_code == 401


def test_get_today_summaries_returns_clean_summary_data(monkeypatch) -> None:
    _set_agent_key(monkeypatch)
    user_id, summary_id, _ = _create_agent_fixture()
    response = client.post("/agent/tools", json={"action": "get_today_summaries", "user_id": user_id, "call_id": "make-test"}, headers=_headers())
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"]
    summaries = payload["data"]["summaries"]
    assert payload["data"]["count"] >= 1
    assert all("subject" in item for item in summaries)
    assert payload["data"]["message"]
    text = response.text.lower()
    assert "refresh_token" not in text
    assert "access_token" not in text
    assert "plain_body" not in text
    assert "anishathahir08@gmail.com" not in payload["message"]
    assert "Re:" not in payload["message"]
    assert "Subject: Project College Update" not in payload["message"]
    assert "Today you have" in payload["message"]


def test_get_today_summaries_returns_clear_zero_message(monkeypatch) -> None:
    _set_agent_key(monkeypatch)
    db = SessionLocal()
    temp_user_email = f"empty-summary-{uuid4()}@example.com"
    try:
        user = User(
            email=temp_user_email,
            name="Empty Summary User",
            phone_number="+919999999999",
            timezone="Asia/Kolkata",
            preferred_language="English",
            hashed_password="temp",
            is_active=True,
            is_verified=False,
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    finally:
        db.close()
    response = client.post(
        "/agent/tools",
        json={"action": "get_today_summaries", "user_id": user.id, "call_id": "zero-summary-test"},
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"] == "You do not have any summarized emails for today."
    assert payload["data"]["count"] == 0
    assert payload["data"]["summaries"] == []
    assert payload["data"]["message"] == "You do not have any summarized emails for today."
    db = SessionLocal()
    try:
        db.query(User).filter(User.email == temp_user_email).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_get_today_summaries_limits_voice_message_to_first_three(monkeypatch) -> None:
    summaries = [
        SimpleNamespace(sender=f"Sender {i} <sender{i}@example.com>", subject=f"Re: Subject {i}", short_summary=f"Short summary {i}", detailed_summary=None, action_required_text=None)
        for i in range(1, 6)
    ]
    message = build_today_summaries_voice_message(summaries)
    assert "Today you have 5 summarized emails" in message
    assert "I will read the first 3" in message
    assert "Email 1" in message
    assert "Email 2" in message
    assert "Email 3" in message
    assert "Email 4" not in message
    assert "Email 5" not in message
    assert "sender1@example.com" not in message
    assert "Re:" not in message
    assert "Sender 1" in message
    assert "Subject 1" in message


def test_get_email_detail_returns_detail(monkeypatch) -> None:
    _set_agent_key(monkeypatch)
    user_id, summary_id, _ = _create_agent_fixture()
    db = SessionLocal()
    try:
        summary = db.query(EmailSummary).filter(EmailSummary.id == summary_id).first()
        assert summary is not None
        summary.sender = "Anisha <anishathahir08@gmail.com>"
        summary.subject = "Re: Specialist - Planning at Flex"
        summary.short_summary = "This email is about a planning specialist role."
        summary.detailed_summary = "This email is about a planning specialist role."
        summary.action_required_text = "No clear action is requested."
        db.add(summary)
        db.commit()
    finally:
        db.close()
    response = client.post(
        "/agent/tools",
        json={"action": "get_email_detail", "user_id": user_id, "email_summary_id": summary_id},
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["message"]
    email = payload["data"]["email"]
    assert email is not None
    assert email["detailed_summary"]
    assert email["short_summary"]
    assert "anishathahir08@gmail.com" not in payload["message"]
    assert "Anisha" in payload["message"]
    assert "Specialist - Planning at Flex" in payload["message"]
    assert "refresh_token" not in response.text.lower()


def test_get_email_detail_returns_friendly_not_found(monkeypatch) -> None:
    _set_agent_key(monkeypatch)
    user = _create_user_if_needed()
    response = client.post(
        "/agent/tools",
        json={"action": "get_email_detail", "user_id": user.id, "email_summary_id": 123456},
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is False
    assert payload["message"] == "I could not find that email summary. Please ask for today's summaries again and choose one from the list."
    assert payload["data"]["email"] is None


def test_search_email_returns_matches(monkeypatch) -> None:
    _set_agent_key(monkeypatch)
    user_id, _, _ = _create_agent_fixture()
    response = client.post(
        "/agent/tools",
        json={"action": "search_email", "user_id": user_id, "query": "college"},
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["matches"]


def test_create_reminder_creates_reminder(monkeypatch) -> None:
    _set_agent_key(monkeypatch)
    user_id, summary_id, _ = _create_agent_fixture()
    response = client.post(
        "/agent/tools",
        json={
            "action": "create_reminder",
            "user_id": user_id,
            "title": "Check project mail",
            "notes": "Follow up with mentor",
            "reminder_time_text": "tomorrow morning",
            "email_summary_id": summary_id,
        },
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["reminder_id"]
    db = SessionLocal()
    try:
        reminder = db.query(Reminder).filter(Reminder.id == payload["data"]["reminder_id"]).first()
        assert reminder is not None
        assert "mentor" in (reminder.notes or "").lower()
    finally:
        db.close()


def test_create_recurring_reminder_creates_rule(monkeypatch) -> None:
    _set_agent_key(monkeypatch)
    user_id, _, _ = _create_agent_fixture()
    response = client.post(
        "/agent/tools",
        json={
            "action": "create_recurring_reminder",
            "user_id": user_id,
            "title": "Daily check-in",
            "notes": "Daily reminder",
            "repeat_type": "daily",
            "time_of_day": "20:00",
            "timezone": "Asia/Kolkata",
        },
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    rule_id = payload["data"]["recurring_rule_id"]
    db = SessionLocal()
    try:
        rule = db.query(RecurringReminderRule).filter(RecurringReminderRule.id == rule_id).first()
        assert rule is not None
        assert rule.title == "Daily check-in"
    finally:
        db.close()


def test_draft_email_reply_creates_draft_only(monkeypatch) -> None:
    _set_agent_key(monkeypatch)
    user_id, summary_id, _ = _create_agent_fixture()
    response = client.post(
        "/agent/tools",
        json={
            "action": "draft_email_reply",
            "user_id": user_id,
            "email_summary_id": summary_id,
            "reply_instruction": "Tell them I will send it tonight",
        },
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    draft_id = payload["data"]["draft_id"]
    db = SessionLocal()
    try:
        draft = db.query(EmailReplyAction).filter(EmailReplyAction.id == draft_id).first()
        assert draft is not None
        assert draft.status == "drafted"
        assert draft.reply_body
    finally:
        db.close()


def test_send_email_reply_sends_only_existing_draft(monkeypatch) -> None:
    _set_agent_key(monkeypatch)
    user_id, summary_id, _ = _create_agent_fixture()
    draft_response = client.post(
        "/agent/tools",
        json={
            "action": "draft_email_reply",
            "user_id": user_id,
            "email_summary_id": summary_id,
            "reply_instruction": "Tell them I will send it tonight",
        },
        headers=_headers(),
    )
    draft_id = draft_response.json()["data"]["draft_id"]

    from app.services import agent_tool_service

    monkeypatch.setattr(agent_tool_service, "_deliver_reply_from_action", lambda db, user, action: "mock-provider-message-id")

    response = client.post(
        "/agent/tools",
        json={"action": "send_email_reply", "user_id": user_id, "draft_id": draft_id},
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["provider_message_id"] == "mock-provider-message-id"


def test_unsupported_action_returns_400(monkeypatch) -> None:
    _set_agent_key(monkeypatch)
    response = client.post("/agent/tools", json={"action": "nope", "user_id": 1}, headers=_headers())
    assert response.status_code == 400


def test_log_call_feedback(monkeypatch) -> None:
    _set_agent_key(monkeypatch)
    user_id, _, call_log_id = _create_agent_fixture()
    response = client.post(
        "/agent/tools",
        json={
            "action": "log_call_feedback",
            "user_id": user_id,
            "call_id": str(call_log_id),
            "feedback_text": "Great call",
            "transcript": "Great call",
            "action_summary": "Positive feedback",
        },
        headers=_headers(),
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["success"] is True
    db = SessionLocal()
    try:
        interaction = db.query(VoiceCallInteraction).filter(VoiceCallInteraction.mail_call_log_id == call_log_id).order_by(VoiceCallInteraction.id.desc()).first()
        assert interaction is not None
        assert interaction.detected_intent == "AGENT_FEEDBACK"
    finally:
        db.close()
