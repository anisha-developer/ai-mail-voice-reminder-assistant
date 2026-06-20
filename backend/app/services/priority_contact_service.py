from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.email_message import EmailMessage
from app.models.email_summary import EmailSummary
from app.models.gmail_connection import GmailConnection
from app.models.priority_contact import PriorityContact
from app.models.priority_mail_alert_log import PriorityMailAlertLog
from app.models.user import User
from app.models.user_call_preference import UserCallPreference
from app.schemas.priority_contact import PriorityContactCreate, PriorityContactUpdate
from app.services.email_summarization_service import summarize_email_ids
from app.services.mail_summary_call_service import prepare_priority_mail_summary_call
from app.services.voice_call_service import start_mail_summary_voice_call

logger = logging.getLogger(__name__)

EMAIL_ADDRESS_RE = re.compile(r"(?<![\w.-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def normalize_email_address(value: str | None) -> str:
    if not value or not isinstance(value, str):
        return ""
    match = EMAIL_ADDRESS_RE.search(value)
    if match:
        return match.group(0).strip().lower()
    return value.strip().lower()


def _display_name_from_email(email: str) -> str:
    candidate = normalize_email_address(email)
    if not candidate:
        return "Unknown sender"
    return candidate.split("@", 1)[0].replace(".", " ").replace("_", " ").strip().title() or "Unknown sender"


def priority_contact_to_item(contact: PriorityContact) -> dict[str, object]:
    return {
        "id": contact.id,
        "user_id": contact.user_id,
        "display_name": contact.display_name,
        "email_address": contact.email_address,
        "relationship": contact.relationship,
        "priority_level": contact.priority_level,
        "notes": contact.notes,
        "created_at": contact.created_at,
        "updated_at": contact.updated_at,
    }


def list_priority_contacts(db: Session, user: User) -> list[PriorityContact]:
    return (
        db.query(PriorityContact)
        .filter(PriorityContact.user_id == user.id)
        .order_by(PriorityContact.created_at.desc(), PriorityContact.id.desc())
        .all()
    )


def get_priority_contact(db: Session, user: User, contact_id: int) -> PriorityContact:
    contact = (
        db.query(PriorityContact)
        .filter(PriorityContact.user_id == user.id, PriorityContact.id == contact_id)
        .first()
    )
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Priority contact not found")
    return contact


def _ensure_unique_email(db: Session, user_id: int, email_address: str, current_id: int | None = None) -> None:
    query = db.query(PriorityContact).filter(PriorityContact.user_id == user_id, PriorityContact.email_address == email_address)
    if current_id is not None:
        query = query.filter(PriorityContact.id != current_id)
    if query.first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Priority contact already exists for this email address")


def create_priority_contact(db: Session, user: User, payload: PriorityContactCreate) -> PriorityContact:
    email_address = normalize_email_address(payload.email_address)
    if not email_address:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email address")
    _ensure_unique_email(db, user.id, email_address)
    contact = PriorityContact(
        user_id=user.id,
        display_name=payload.display_name.strip(),
        email_address=email_address,
        relationship=payload.relationship or "Other",
        priority_level=int(payload.priority_level or 1),
        notes=(payload.notes or "").strip() or None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def update_priority_contact(db: Session, user: User, contact_id: int, payload: PriorityContactUpdate) -> PriorityContact:
    contact = get_priority_contact(db, user, contact_id)
    if payload.email_address is not None:
        email_address = normalize_email_address(payload.email_address)
        if not email_address:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email address")
        _ensure_unique_email(db, user.id, email_address, current_id=contact.id)
        contact.email_address = email_address
    if payload.display_name is not None:
        contact.display_name = payload.display_name.strip()
    if payload.relationship is not None:
        contact.relationship = (payload.relationship or "Other").strip() or "Other"
    if payload.priority_level is not None:
        contact.priority_level = int(payload.priority_level)
    if payload.notes is not None:
        contact.notes = payload.notes.strip() or None
    contact.updated_at = datetime.now(timezone.utc)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def delete_priority_contact(db: Session, user: User, contact_id: int) -> PriorityContact:
    contact = get_priority_contact(db, user, contact_id)
    db.delete(contact)
    db.commit()
    return contact


def find_priority_contact_for_sender(db: Session, user_id: int, sender: str | None) -> PriorityContact | None:
    sender_email = normalize_email_address(sender)
    if not sender_email:
        return None
    return (
        db.query(PriorityContact)
        .filter(PriorityContact.user_id == user_id, PriorityContact.email_address == sender_email)
        .first()
    )


def _priority_alert_log_exists(db: Session, email_message_id: int) -> bool:
    return (
        db.query(PriorityMailAlertLog.id)
        .filter(PriorityMailAlertLog.email_message_id == email_message_id)
        .first()
        is not None
    )


def _user_has_priority_phone(db: Session, user: User) -> bool:
    prefs = db.query(UserCallPreference).filter(UserCallPreference.user_id == user.id).first()
    return bool(prefs and prefs.phone_number)


def _gmail_connected(db: Session, user: User) -> bool:
    return (
        db.query(GmailConnection.id)
        .filter(GmailConnection.user_id == user.id, GmailConnection.is_connected.is_(True))
        .first()
        is not None
    )


def _summary_for_email(db: Session, user: User, email_message_id: int) -> EmailSummary | None:
    summary = db.query(EmailSummary).filter(EmailSummary.user_id == user.id, EmailSummary.email_message_id == email_message_id).first()
    if summary is not None:
        return summary
    result = summarize_email_ids(db, user, [email_message_id])
    if result.get("success_count", 0) or result.get("processed_count", 0):
        return db.query(EmailSummary).filter(EmailSummary.user_id == user.id, EmailSummary.email_message_id == email_message_id).first()
    return None


def process_priority_email_alert(db: Session, user: User, email_message: EmailMessage) -> dict[str, object]:
    contact = find_priority_contact_for_sender(db, user.id, email_message.sender)
    if contact is None:
        return {"success": False, "status": "not_priority", "message": "No matching priority contact."}
    if _priority_alert_log_exists(db, email_message.id):
        return {"success": False, "status": "duplicate", "message": "Priority alert already triggered."}
    if not _gmail_connected(db, user):
        return {"success": False, "status": "gmail_disconnected", "message": "Gmail is not connected."}
    if not _user_has_priority_phone(db, user):
        return {"success": False, "status": "missing_phone", "message": "No call preference phone number configured."}

    summary = _summary_for_email(db, user, email_message.id)
    if summary is None:
        logger.warning(
            "Priority alert skipped because summary is unavailable for email_id=%s user_id=%s sender=%s",
            email_message.id,
            user.id,
            (email_message.sender or "")[:120],
        )
        return {"success": False, "status": "summary_unavailable", "message": "Priority summary is unavailable."}

    prepared = prepare_priority_mail_summary_call(db, user, summary, contact=contact)
    alert_log = PriorityMailAlertLog(
        user_id=user.id,
        email_message_id=email_message.id,
        priority_contact_id=contact.id,
        mail_call_log_id=prepared["call_log_id"],
        status="triggered",
        error_message=None,
        triggered_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(alert_log)
    db.commit()
    db.refresh(alert_log)

    try:
        call_result = start_mail_summary_voice_call(db, user, prepared["call_log_id"], call_purpose="priority_contact_mail_alert")
    except Exception as exc:
        alert_log.status = "failed"
        alert_log.error_message = f"{type(exc).__name__}: {exc}"
        alert_log.updated_at = datetime.now(timezone.utc)
        db.add(alert_log)
        db.commit()
        logger.warning(
            "Priority alert call failed email_id=%s user_id=%s contact_id=%s error=%s: %s",
            email_message.id,
            user.id,
            contact.id,
            type(exc).__name__,
            exc,
        )
        return {"success": False, "status": "failed", "message": "Priority call could not be sent."}

    alert_log.status = call_result.get("status") or "queued"
    alert_log.updated_at = datetime.now(timezone.utc)
    db.add(alert_log)
    db.commit()
    return {
        "success": True,
        "status": call_result.get("status") or "queued",
        "message": "Priority contact alert call queued.",
        "call_log_id": prepared["call_log_id"],
    }

