from __future__ import annotations

import base64
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import parseaddr

from fastapi import HTTPException, status
from sqlalchemy.exc import OperationalError, ProgrammingError
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.models.email_reply_action import EmailReplyAction
from app.models.email_message import EmailMessage as GmailEmailMessage
from app.models.email_summary import EmailSummary
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.voice_reply_session import VoiceReplySession
from app.models.user import User
from app.services.gmail_oauth_service import get_connection_credentials


def _active_session(db: Session, user_id: int, call_log_id: int) -> VoiceReplySession | None:
    try:
        return (
            db.query(VoiceReplySession)
            .filter(
                VoiceReplySession.user_id == user_id,
                VoiceReplySession.mail_call_log_id == call_log_id,
                VoiceReplySession.status.in_(["awaiting_body", "awaiting_confirmation"]),
            )
            .order_by(VoiceReplySession.id.desc())
            .first()
        )
    except (OperationalError, ProgrammingError):
        db.rollback()
        return None


def get_active_reply_session(db: Session, user: User, call_log: MailSummaryCallLog) -> VoiceReplySession | None:
    return _active_session(db, user.id, call_log.id)


def _extract_email_address(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    display_name, email_addr = parseaddr(raw)
    candidate = (email_addr or "").strip()
    if "@" in candidate:
        return candidate
    if "@" in raw and "<" not in raw and ">" not in raw:
        return raw
    if display_name and "@" in display_name:
        return display_name.strip()
    return None


def resolve_reply_recipient(email_message: GmailEmailMessage | None) -> str | None:
    if email_message is None:
        return None
    for candidate in (getattr(email_message, "reply_to", None), email_message.sender):
        resolved = _extract_email_address(candidate)
        if resolved:
            return resolved
    return None


def start_reply_session(
    db: Session,
    user: User,
    call_log: MailSummaryCallLog,
    target_email_summary: EmailSummary,
    reply_body: str | None = None,
    target_email_reference: int | None = None,
) -> VoiceReplySession:
    session = VoiceReplySession(
        user_id=user.id,
        mail_call_log_id=call_log.id,
        email_message_id=target_email_summary.email_message_id,
        email_summary_id=target_email_summary.id,
        target_email_reference=target_email_reference,
        reply_body=reply_body,
        status="awaiting_confirmation" if reply_body else "awaiting_body",
        gmail_thread_id=target_email_summary.email_message.gmail_thread_id if target_email_summary.email_message else None,
        gmail_message_id=target_email_summary.email_message.gmail_message_id if target_email_summary.email_message else None,
        to_email=resolve_reply_recipient(target_email_summary.email_message),
        subject=target_email_summary.subject,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def update_reply_body(db: Session, session: VoiceReplySession, reply_body: str) -> VoiceReplySession:
    session.reply_body = reply_body.strip()
    session.status = "awaiting_confirmation"
    session.updated_at = datetime.now(timezone.utc)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def cancel_reply(db: Session, session: VoiceReplySession, reason: str | None = None) -> VoiceReplySession:
    session.status = "cancelled"
    session.last_error = reason
    session.updated_at = datetime.now(timezone.utc)
    db.add(session)
    action = EmailReplyAction(
        user_id=session.user_id,
        email_message_id=session.email_message_id,
        mail_call_log_id=session.mail_call_log_id,
        voice_reply_session_id=session.id,
        gmail_message_id=session.gmail_message_id,
        gmail_thread_id=session.gmail_thread_id,
        reply_body=session.reply_body,
        status="cancelled",
        error_message=reason,
        created_at=datetime.now(timezone.utc),
    )
    db.add(action)
    db.commit()
    db.refresh(session)
    return session


def _build_raw_message(user: User, session: VoiceReplySession, reply_body: str) -> str:
    if not session.to_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="I could not find a valid recipient for this reply. Please choose a different email.",
        )
    msg = EmailMessage()
    msg["To"] = session.to_email
    subject = session.subject or "Re: your email"
    if not subject.lower().startswith("re:"):
        subject = f"Re: {subject}"
    msg["Subject"] = subject
    msg["From"] = user.email
    msg.set_content(reply_body)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def send_reply(db: Session, user: User, session: VoiceReplySession) -> dict[str, object]:
    if session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You cannot send a reply for another user")
    if session.status != "awaiting_confirmation":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reply is not ready to send")
    if not session.reply_body:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reply body is missing")
    recipient = resolve_reply_recipient(session.email_message) or (session.to_email.strip() if session.to_email else None)
    if not recipient:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="I could not find a valid recipient for this reply. Please choose a different email.",
        )
    session.to_email = recipient
    session.updated_at = datetime.now(timezone.utc)
    db.add(session)
    creds = get_connection_credentials(db, user.id)
    if creds is None or not creds.refresh_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="I need Gmail send permission before I can send replies. Please reconnect Gmail from the dashboard.")
    if "https://www.googleapis.com/auth/gmail.send" not in (creds.scopes or []):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="I need Gmail send permission before I can send replies. Please reconnect Gmail from the dashboard.")

    gmail_service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    raw_message = _build_raw_message(user, session, session.reply_body)
    try:
        sent_message = gmail_service.users().messages().send(userId="me", body={"raw": raw_message, "threadId": session.gmail_thread_id}).execute()
    except Exception as exc:
        session.status = "failed"
        session.last_error = str(exc)
        session.updated_at = datetime.now(timezone.utc)
        db.add(session)
        action = EmailReplyAction(
            user_id=session.user_id,
            email_message_id=session.email_message_id,
            mail_call_log_id=session.mail_call_log_id,
            voice_reply_session_id=session.id,
            gmail_message_id=session.gmail_message_id,
            gmail_thread_id=session.gmail_thread_id,
            reply_body=session.reply_body,
            status="failed",
            error_message=str(exc),
            created_at=datetime.now(timezone.utc),
        )
        db.add(action)
        db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Gmail reply failed") from exc

    session.status = "sent"
    session.sent_at = datetime.now(timezone.utc)
    session.updated_at = datetime.now(timezone.utc)
    db.add(session)
    action = EmailReplyAction(
        user_id=session.user_id,
        email_message_id=session.email_message_id,
        mail_call_log_id=session.mail_call_log_id,
        voice_reply_session_id=session.id,
        gmail_message_id=session.gmail_message_id,
        gmail_thread_id=session.gmail_thread_id,
        reply_body=session.reply_body,
        status="sent",
        provider_message_id=sent_message.get("id"),
        created_at=datetime.now(timezone.utc),
        sent_at=datetime.now(timezone.utc),
    )
    db.add(action)
    db.commit()
    return {"provider_message_id": sent_message.get("id")}


def list_reply_actions(db: Session, user: User) -> list[EmailReplyAction]:
    try:
        return db.query(EmailReplyAction).filter(EmailReplyAction.user_id == user.id).order_by(EmailReplyAction.id.desc()).all()
    except (OperationalError, ProgrammingError):
        db.rollback()
        return []


def get_reply_action(db: Session, user: User, action_id: int) -> EmailReplyAction:
    try:
        action = db.query(EmailReplyAction).filter(EmailReplyAction.user_id == user.id, EmailReplyAction.id == action_id).first()
    except (OperationalError, ProgrammingError):
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Reply history is unavailable")
    if action is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reply action not found")
    return action
