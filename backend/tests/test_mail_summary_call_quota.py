from __future__ import annotations

from datetime import date, datetime, time, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.database.session import SessionLocal
from app.models.email_message import EmailMessage
from app.models.email_summary import EmailSummary
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.user import User
from app.models.user_call_preference import UserCallPreference
from app.services.email_summarization_service import get_summary_counts
from app.services.mail_summary_call_service import get_mail_call_count_today, prepare_mail_summary_call


def _create_user(email_prefix: str = "quota-test") -> dict[str, object]:
    db = SessionLocal()
    try:
        user = User(
            email=f"{email_prefix}-{uuid4()}@example.com",
            name="Quota Test User",
            phone_number="+919843731545",
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
        user_id = user.id
        user_email = user.email
        phone_number = user.phone_number
        db.add(
            UserCallPreference(
                user_id=user_id,
                timezone="Asia/Kolkata",
                call_slot_1_time="09:00",
                call_slot_1_enabled=True,
                call_slot_2_time="12:30",
                call_slot_2_enabled=True,
                call_slot_3_time="14:02",
                call_slot_3_enabled=True,
                minimum_new_emails_to_call=1,
                skip_if_no_new_emails=True,
                avoid_repeating_delivered_emails=True,
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.commit()
        return {"id": user_id, "email": user_email, "phone_number": phone_number}
    finally:
        db.close()


def _cleanup_user(user_id: int) -> None:
    db = SessionLocal()
    try:
        db.query(MailSummaryCallLog).filter(MailSummaryCallLog.user_id == user_id).delete(synchronize_session=False)
        db.query(EmailSummary).filter(EmailSummary.user_id == user_id).delete(synchronize_session=False)
        db.query(EmailMessage).filter(EmailMessage.user_id == user_id).delete(synchronize_session=False)
        db.query(UserCallPreference).filter(UserCallPreference.user_id == user_id).delete(synchronize_session=False)
        db.query(User).filter(User.id == user_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _create_summary(db, user_id: int, user_email: str, subject: str = "Quota test email") -> EmailSummary:
    message = EmailMessage(
        user_id=user_id,
        gmail_message_id=f"quota-test-{uuid4()}",
        gmail_thread_id=f"thread-{uuid4()}",
        sender="sender@example.com",
        recipient=user_email,
        subject=subject,
        snippet="Snippet",
        plain_body="Body",
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
        user_id=user_id,
        email_message_id=message.id,
        sender=message.sender,
        subject=message.subject,
        short_summary="Short summary",
        detailed_summary="Detailed summary",
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
    return summary


def test_mail_call_count_today_counts_only_current_enabled_slots() -> None:
    user = _create_user("quota-count")
    db = SessionLocal()
    try:
        user_id = int(user["id"])
        delivered_times = [
            (time(9, 0), "delivered"),
            (time(11, 40), "delivered"),
            (time(18, 14), "completed"),
        ]
        for call_time, call_status in delivered_times:
            db.add(
                MailSummaryCallLog(
                    user_id=user_id,
                    call_type="mail_summary",
                    call_status=call_status,
                    call_date=date.today(),
                    call_time=call_time,
                    summary_count=1,
                    script_text="Quota test",
                    delivery_status="delivered",
                    delivered_summary_ids="[]",
                    provider="twilio",
                    provider_call_id=f"CA-{uuid4()}",
                    to_phone_number=str(user["phone_number"]),
                    from_phone_number="+17154196839",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
        db.commit()

        current_user = db.query(User).filter(User.id == user_id).first()
        assert current_user is not None
        counts = get_mail_call_count_today(db, current_user)
        assert counts["used_calls_today"] == 1
        assert counts["remaining_calls_today"] == 2
    finally:
        _cleanup_user(int(user["id"]))


def test_prepare_mail_summary_call_blocks_only_when_three_current_slots_used() -> None:
    user = _create_user("quota-prepare")
    db = SessionLocal()
    try:
        user_id = int(user["id"])
        summary = _create_summary(db, user_id, str(user["email"]))
        db.add(
            MailSummaryCallLog(
                user_id=user_id,
                call_type="mail_summary",
                call_status="delivered",
                call_date=date.today(),
                call_time=time(9, 0),
                summary_count=1,
                script_text="Quota test",
                delivery_status="delivered",
                delivered_summary_ids="[]",
                provider="twilio",
                provider_call_id=f"CA-{uuid4()}",
                to_phone_number=str(user["phone_number"]),
                from_phone_number="+17154196839",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            MailSummaryCallLog(
                user_id=user_id,
                call_type="mail_summary",
                call_status="delivered",
                call_date=date.today(),
                call_time=time(12, 30),
                summary_count=1,
                script_text="Quota test",
                delivery_status="delivered",
                delivered_summary_ids="[]",
                provider="twilio",
                provider_call_id=f"CA-{uuid4()}",
                to_phone_number=str(user["phone_number"]),
                from_phone_number="+17154196839",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.add(
            MailSummaryCallLog(
                user_id=user_id,
                call_type="mail_summary",
                call_status="completed",
                call_date=date.today(),
                call_time=time(14, 2),
                summary_count=1,
                script_text="Quota test",
                delivery_status="delivered",
                delivered_summary_ids="[]",
                provider="twilio",
                provider_call_id=f"CA-{uuid4()}",
                to_phone_number=str(user["phone_number"]),
                from_phone_number="+17154196839",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

        current_user = db.query(User).filter(User.id == user_id).first()
        assert current_user is not None
        with pytest.raises(HTTPException) as exc_info:
            prepare_mail_summary_call(db, current_user)
        assert exc_info.value.status_code == 400
        assert "limit reached" in str(exc_info.value.detail).lower()
    finally:
        _cleanup_user(int(user["id"]))


def test_summary_counts_exclude_historical_non_inbox_messages() -> None:
    user = _create_user("quota-summary-consistency")
    db = SessionLocal()
    try:
        user_id = int(user["id"])
        current_user = db.query(User).filter(User.id == user_id).first()
        assert current_user is not None

        active_today = _create_summary(db, user_id, str(user["email"]), subject="Active today summary")
        stale_not_inbox = _create_summary(db, user_id, str(user["email"]), subject="Old removed summary")

        active_message = db.query(EmailMessage).filter(EmailMessage.id == active_today.email_message_id).first()
        stale_message = db.query(EmailMessage).filter(EmailMessage.id == stale_not_inbox.email_message_id).first()
        assert active_message is not None and stale_message is not None

        active_message.received_at = datetime.now(timezone.utc)
        active_message.is_in_inbox = True
        stale_message.received_at = datetime.now(timezone.utc)
        stale_message.is_in_inbox = False
        db.add(active_message)
        db.add(stale_message)
        db.commit()

        counts = get_mail_call_count_today(db, current_user)
        summary_counts = get_summary_counts(db, user_id)

        assert counts["today_summaries_count"] == 1
        assert counts["pending_today_summaries_count"] == 1
        assert summary_counts["generated_today"] == 1
    finally:
        _cleanup_user(int(user["id"]))
