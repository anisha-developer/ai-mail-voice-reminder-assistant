from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.database.session import SessionLocal
from app.models.email_message import EmailMessage
from app.models.email_summary import EmailSummary
from app.models.gmail_connection import GmailConnection
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.user import User
from app.models.user_call_preference import UserCallPreference
from app.services import call_preferences_service as cps
from app.services.voice_call_service import start_mail_summary_voice_call


def _create_user(phone_number: str, call_phone_number: str, slot_time: str = "09:00") -> tuple[int, str]:
    db = SessionLocal()
    try:
        email = f"phone-pref-{uuid4()}@example.com"
        user = User(
            email=email,
            name="Phone Pref User",
            phone_number=phone_number,
            timezone="Asia/Kolkata",
            preferred_language="English",
            hashed_password="hash",
            is_active=True,
            is_verified=True,
            created_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.add(
            GmailConnection(
                user_id=user.id,
                gmail_email=email,
                access_token_encrypted="encrypted-access",
                refresh_token_encrypted="encrypted-refresh",
                token_uri="https://oauth2.googleapis.com/token",
                scopes="scope",
                expiry=datetime.now(timezone.utc) + timedelta(hours=1),
                is_connected=True,
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            UserCallPreference(
                user_id=user.id,
                phone_number=call_phone_number,
                timezone="Asia/Kolkata",
                call_slot_1_time=slot_time,
                call_slot_1_enabled=True,
                call_slot_2_time="13:00",
                call_slot_2_enabled=False,
                call_slot_3_time="19:00",
                call_slot_3_enabled=False,
                minimum_new_emails_to_call=1,
                skip_if_no_new_emails=True,
                avoid_repeating_delivered_emails=True,
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        return user.id, email
    finally:
        db.close()


def _create_prepared_call_log(user_id: int, summary_count: int = 1) -> int:
    db = SessionLocal()
    try:
        call_log = MailSummaryCallLog(
            user_id=user_id,
            call_type="mail_summary",
            call_status="prepared",
            call_date=date.today(),
            call_time=time(9, 0),
            summary_count=summary_count,
            script_text="Hello. You received 1 emails today.",
            delivery_status="pending",
            delivered_summary_ids="[]",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(call_log)
        db.commit()
        db.refresh(call_log)
        return call_log.id
    finally:
        db.close()


def _patch_twilio(monkeypatch, captured: dict[str, object]) -> None:
    class DummyCalls:
        def create(self, **kwargs):
            captured["kwargs"] = kwargs
            return SimpleNamespace(sid="CA1234567890", status="queued")

    class DummyClient:
        calls = DummyCalls()

    monkeypatch.setattr("app.services.voice_call_service._require_twilio_config", lambda: None)
    monkeypatch.setattr("app.services.voice_call_service._twilio_client", lambda: DummyClient())
    monkeypatch.setattr("app.services.voice_call_service.settings", SimpleNamespace(twilio_from_phone="+17154196839", public_backend_url="https://example.com", mail_call_provider="twilio"))


def _cleanup_user(user_id: int) -> None:
    db = SessionLocal()
    try:
        db.query(MailSummaryCallLog).filter(MailSummaryCallLog.user_id == user_id).delete(synchronize_session=False)
        db.query(EmailSummary).filter(EmailSummary.user_id == user_id).delete(synchronize_session=False)
        db.query(EmailMessage).filter(EmailMessage.user_id == user_id).delete(synchronize_session=False)
        db.query(UserCallPreference).filter(UserCallPreference.user_id == user_id).delete(synchronize_session=False)
        db.query(GmailConnection).filter(GmailConnection.user_id == user_id).delete(synchronize_session=False)
        db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def test_start_mail_summary_voice_call_uses_call_preference_phone_number(monkeypatch) -> None:
    user_id, _ = _create_user("+919999999999", "+918888888888")
    call_log_id = _create_prepared_call_log(user_id)
    captured: dict[str, object] = {}
    _patch_twilio(monkeypatch, captured)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        assert user is not None
        result = start_mail_summary_voice_call(db, user, call_log_id)
        assert result["provider"] == "twilio"
        assert captured["kwargs"]["to"] == "+918888888888"
    finally:
        db.close()
        _cleanup_user(user_id)


def test_run_due_mail_summary_calls_uses_call_preference_phone_number(monkeypatch) -> None:
    slot_time = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M")
    user_id, _ = _create_user("+919999999999", "+918888888888", slot_time=slot_time)
    call_log_id = _create_prepared_call_log(user_id)
    captured: dict[str, object] = {}
    _patch_twilio(monkeypatch, captured)

    monkeypatch.setattr(cps, "get_mail_call_count_today", lambda db, user: {"used_calls_today": 0})
    monkeypatch.setattr(cps, "list_pending_today_summaries", lambda db, user: [object()])
    monkeypatch.setattr(cps, "list_todays_summaries", lambda db, user: [object()])
    monkeypatch.setattr(cps, "_mail_summary_call_exists_for_slot", lambda db, user_id, call_date, slot_time: False)

    def fake_prepare(db, user, include_delivered=False):
        return {"call_log_id": call_log_id}

    monkeypatch.setattr(cps, "prepare_mail_summary_call", fake_prepare)

    cps.run_due_mail_summary_calls()
    assert captured["kwargs"]["to"] == "+918888888888"
    _cleanup_user(user_id)
