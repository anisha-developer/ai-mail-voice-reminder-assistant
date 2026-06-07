from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from app.database.session import SessionLocal
from app.models.email_message import EmailMessage
from app.models.email_summary import EmailSummary
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.user import User
from app.services.voice_email_lookup_service import resolve_email_reference_for_call
from app.services.voice_intent_service import LOOKUP_FIRST, LOOKUP_LAST, LOOKUP_LATEST, LOOKUP_KEYWORD, LOOKUP_SENDER, LOOKUP_SUBJECT, ParsedVoiceIntent


def _create_lookup_fixture() -> tuple[int, list[int], list[int]]:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        assert user is not None

        message_specs = [
            ("Google", "Google account security alert", "google security", "Detailed Google security email"),
            ("Amazon", "Your Amazon order update", "amazon order", "Detailed Amazon order email"),
            ("Kaggle Team", "Fwd: Kaggle notebook", "kaggle notebook", "Detailed Kaggle notebook email"),
            ("Mentor", "Project assignment review", "assignment project", "Detailed assignment mail"),
            ("College Admin", "Final Auto Sync Summary Test", "auto sync test final", "Detailed auto sync test email"),
        ]

        message_ids: list[int] = []
        summary_ids: list[int] = []
        for index, (sender, subject, short_summary, detailed_summary) in enumerate(message_specs, start=1):
            message = EmailMessage(
                user_id=user.id,
                gmail_message_id=f"phase10-{uuid4()}",
                gmail_thread_id=None,
                sender=sender,
                recipient=user.email,
                subject=subject,
                snippet=short_summary,
                plain_body=short_summary,
                html_body=None,
                received_at=datetime.now(timezone.utc) - timedelta(minutes=10 - index),
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
                sender=sender,
                subject=subject,
                short_summary=short_summary,
                detailed_summary=detailed_summary,
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
            call_time=datetime.now(timezone.utc).time().replace(microsecond=0),
            summary_count=len(summary_ids),
            script_text="Test script",
            delivery_status="pending",
            delivered_summary_ids=json.dumps(summary_ids),
            failure_reason=None,
            provider="twilio",
            provider_call_id=f"CA-{uuid4()}",
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


def _cleanup_lookup_fixture(call_log_id: int, summary_ids: list[int], message_ids: list[int]) -> None:
    db = SessionLocal()
    try:
        db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).delete(synchronize_session=False)
        db.query(EmailSummary).filter(EmailSummary.id.in_(summary_ids)).delete(synchronize_session=False)
        db.query(EmailMessage).filter(EmailMessage.id.in_(message_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _intent(transcript: str, lookup_type: str | None = None, **kwargs) -> ParsedVoiceIntent:
    from app.services.voice_intent_service import parse_voice_intent

    parsed = parse_voice_intent(transcript)
    if lookup_type is not None:
        assert parsed.lookup_type == lookup_type
    for key, value in kwargs.items():
        assert getattr(parsed, key) == value
    return parsed


def test_sender_subject_keyword_latest_first_last_lookup_resolution() -> None:
    call_log_id, summary_ids, message_ids = _create_lookup_fixture()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        call_log = db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).first()
        assert user is not None and call_log is not None

        sender_intent = _intent("explain the email from Google", LOOKUP_SENDER)
        sender_result = resolve_email_reference_for_call(db, user, call_log, sender_intent)
        assert sender_result["status"] in {"matched", "multiple_matches"}
        assert sender_result["matches"]

        subject_intent = _intent("explain Kaggle notebook email", LOOKUP_SUBJECT)
        subject_result = resolve_email_reference_for_call(db, user, call_log, subject_intent)
        assert subject_result["status"] == "matched"
        assert subject_result["email_reference"] == 3

        keyword_intent = _intent("tell me about assignment mail")
        assert keyword_intent.lookup_type in {LOOKUP_KEYWORD, LOOKUP_SUBJECT}
        keyword_result = resolve_email_reference_for_call(db, user, call_log, keyword_intent)
        assert keyword_result["status"] == "matched"
        assert keyword_result["email_reference"] == 4

        latest_intent = _intent("read latest email", LOOKUP_LATEST)
        latest_result = resolve_email_reference_for_call(db, user, call_log, latest_intent)
        assert latest_result["status"] == "matched"
        assert latest_result["email_reference"] == 5

        first_intent = _intent("explain first mail", LOOKUP_FIRST)
        first_result = resolve_email_reference_for_call(db, user, call_log, first_intent)
        assert first_result["status"] == "matched"
        assert first_result["email_reference"] == 1

        last_intent = _intent("read last email", LOOKUP_LAST)
        last_result = resolve_email_reference_for_call(db, user, call_log, last_intent)
        assert last_result["status"] == "matched"
        assert last_result["email_reference"] == 5

        no_match_intent = _intent("bank loan statement", None)
        no_match_result = resolve_email_reference_for_call(db, user, call_log, no_match_intent)
        assert no_match_result["status"] == "no_match"

        invalid_intent = ParsedVoiceIntent(
            intent="DETAIL_EMAIL",
            email_reference=20,
            confidence=0.9,
            normalized_transcript="explain email number 20",
            reason="test",
            lookup_query="20",
            lookup_type="number",
            ordinal_reference="20",
        )
        invalid_result = resolve_email_reference_for_call(db, user, call_log, invalid_intent)
        assert invalid_result["status"] == "invalid_reference"
    finally:
        db.close()
        _cleanup_lookup_fixture(call_log_id, summary_ids, message_ids)


def test_multiple_matches_resolution() -> None:
    call_log_id, summary_ids, message_ids = _create_lookup_fixture()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "browsertest@example.com").first()
        call_log = db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == call_log_id).first()
        assert user is not None and call_log is not None
        parsed = _intent("read mail from Google", LOOKUP_SENDER)
        result = resolve_email_reference_for_call(db, user, call_log, parsed)
        assert result["status"] in {"matched", "multiple_matches"}
        assert result["matches"]
    finally:
        db.close()
        _cleanup_lookup_fixture(call_log_id, summary_ids, message_ids)
