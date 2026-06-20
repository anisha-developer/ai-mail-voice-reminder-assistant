from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import OperationalError, ProgrammingError, IntegrityError
from sqlalchemy.orm import Session

from app.models.email_summary import EmailSummary
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.voice_email_reply_log import VoiceEmailReplyLog
from app.models.user import User


def _normalize_text(value: str | None) -> str:
    return " ".join((value or "").split())


def _get_call_log(db: Session, user: User, call_log_id: int) -> MailSummaryCallLog:
    call_log = (
        db.query(MailSummaryCallLog)
        .filter(MailSummaryCallLog.id == call_log_id, MailSummaryCallLog.user_id == user.id, MailSummaryCallLog.call_type == "mail_summary")
        .first()
    )
    if call_log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mail summary call not found")
    return call_log


def _summary_for_reference(db: Session, call_log: MailSummaryCallLog, email_number: int) -> EmailSummary:
    summary_ids = []
    try:
        payload = json.loads(call_log.delivered_summary_ids or "[]")
        if isinstance(payload, list):
            summary_ids = [int(value) for value in payload]
    except Exception:
        summary_ids = []
    if email_number < 1 or email_number > len(summary_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email number not found")
    summary_id = summary_ids[email_number - 1]
    summary = db.query(EmailSummary).filter(EmailSummary.id == summary_id, EmailSummary.user_id == call_log.user_id).first()
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email number not found")
    return summary


def _find_existing_log(
    db: Session,
    user_id: int,
    mail_call_id: int | str,
    email_number: int,
    reply_text: str,
    source: str,
) -> VoiceEmailReplyLog | None:
    try:
        return (
            db.query(VoiceEmailReplyLog)
            .filter(
                VoiceEmailReplyLog.user_id == user_id,
                VoiceEmailReplyLog.mail_call_id == str(mail_call_id),
                VoiceEmailReplyLog.email_number == email_number,
                VoiceEmailReplyLog.reply_text == reply_text,
                VoiceEmailReplyLog.source == source,
            )
            .order_by(VoiceEmailReplyLog.id.desc())
            .first()
        )
    except (OperationalError, ProgrammingError):
        db.rollback()
        return None


def create_reply_status_log(
    db: Session,
    user: User,
    call_log: MailSummaryCallLog,
    summary: EmailSummary,
    email_number: int,
    reply_text: str,
    call_id: int | str | None,
    source: str = "voice_call",
) -> VoiceEmailReplyLog:
    normalized_reply = _normalize_text(reply_text)
    existing = _find_existing_log(db, user.id, call_log.id, email_number, normalized_reply, source)
    if existing is not None:
        return existing
    log = VoiceEmailReplyLog(
        user_id=user.id,
        mail_call_id=str(call_log.id),
        call_id=str(call_id) if call_id is not None else None,
        email_number=email_number,
        original_email_id=summary.email_message_id,
        original_summary_id=summary.id,
        original_sender=summary.sender,
        original_subject=summary.subject,
        reply_text=normalized_reply,
        status="pending",
        source=source,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def mark_reply_status_sent(db: Session, log: VoiceEmailReplyLog, sent_at: datetime | None = None) -> VoiceEmailReplyLog:
    log.status = "sent"
    log.failure_reason = None
    log.sent_at = sent_at or datetime.now(timezone.utc)
    log.updated_at = datetime.now(timezone.utc)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def mark_reply_status_failed(db: Session, log: VoiceEmailReplyLog, failure_reason: str | None) -> VoiceEmailReplyLog:
    log.status = "failed"
    log.failure_reason = failure_reason
    log.updated_at = datetime.now(timezone.utc)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def list_reply_status_logs(db: Session, user: User, status_filter: str | None = None, source_filter: str | None = None) -> list[VoiceEmailReplyLog]:
    try:
        query = db.query(VoiceEmailReplyLog).filter(VoiceEmailReplyLog.user_id == user.id)
        if status_filter:
            query = query.filter(VoiceEmailReplyLog.status == status_filter)
        if source_filter:
            query = query.filter(VoiceEmailReplyLog.source == source_filter)
        return query.order_by(VoiceEmailReplyLog.id.desc()).all()
    except (OperationalError, ProgrammingError):
        db.rollback()
        return []


def get_reply_status_log(db: Session, user: User, log_id: int) -> VoiceEmailReplyLog:
    try:
        log = db.query(VoiceEmailReplyLog).filter(VoiceEmailReplyLog.user_id == user.id, VoiceEmailReplyLog.id == log_id).first()
    except (OperationalError, ProgrammingError):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Reply status history is unavailable")
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reply status not found")
    return log


def build_reply_status_item(log: VoiceEmailReplyLog) -> dict[str, Any]:
    return {
        "id": log.id,
        "mail_call_id": log.mail_call_id,
        "call_id": log.call_id,
        "email_number": log.email_number,
        "original_email_id": log.original_email_id,
        "original_summary_id": log.original_summary_id,
        "original_sender": log.original_sender,
        "original_subject": log.original_subject,
        "reply_text": log.reply_text,
        "status": log.status,
        "failure_reason": log.failure_reason,
        "source": log.source,
        "created_at": log.created_at,
        "updated_at": log.updated_at,
        "sent_at": log.sent_at,
    }
