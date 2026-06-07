from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.core.encryption import decrypt_value
from app.models.email_message import EmailMessage
from app.models.gmail_connection import GmailConnection
from app.models.user import User
from app.services.gmail_oauth_service import refresh_access_token_if_needed

logger = logging.getLogger(__name__)


def _decode_base64url(value: str | None) -> str:
    if not value:
        return ""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode()).decode("utf-8", errors="ignore")


def _extract_parts(payload: dict) -> tuple[str | None, str | None, list[dict]]:
    plain_body = None
    html_body = None
    attachments: list[dict] = []

    def walk(part: dict) -> None:
        nonlocal plain_body, html_body
        mime_type = part.get("mimeType", "")
        filename = part.get("filename") or ""
        body = part.get("body") or {}

        if part.get("parts"):
            for child in part.get("parts", []):
                walk(child)
            return

        if body.get("attachmentId") or filename:
            attachments.append(
                {
                    "filename": filename or None,
                    "mime_type": mime_type or None,
                    "attachment_id": body.get("attachmentId"),
                    "size": body.get("size"),
                }
            )

        data = _decode_base64url(body.get("data"))
        if mime_type == "text/plain" and data and plain_body is None:
            plain_body = data
        elif mime_type == "text/html" and data and html_body is None:
            html_body = data

    walk(payload)
    return plain_body, html_body, attachments


def _get_connection(db: Session, user_id: int) -> GmailConnection | None:
    return db.query(GmailConnection).filter(GmailConnection.user_id == user_id, GmailConnection.is_connected.is_(True)).first()


def _gmail_service_for_user(db: Session, user_id: int):
    connection = _get_connection(db, user_id)
    if connection is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail account is not connected.")

    creds = refresh_access_token_if_needed(db, user_id)
    if creds is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail connection expired. Please reconnect Gmail.")

    if not creds.token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Gmail connection expired. Please reconnect Gmail.")

    return build("gmail", "v1", credentials=creds, cache_discovery=False), connection


def _latest_stored_received_at(db: Session, user_id: int):
    latest = (
        db.query(EmailMessage)
        .filter(EmailMessage.user_id == user_id)
        .order_by(EmailMessage.received_at.desc().nullslast(), EmailMessage.id.desc())
        .first()
    )
    return latest.received_at if latest else None


def sync_user_emails(db: Session, user: User, max_results: int = 50, max_pages: int = 3) -> dict[str, int | str | None | list[int] | list[str]]:
    gmail_service, _connection = _gmail_service_for_user(db, user.id)
    processed = 0
    inserted = 0
    duplicates = 0
    gmail_message_ids: list[str] = []
    inserted_email_ids: list[int] = []
    inserted_gmail_message_ids: list[str] = []
    latest_gmail_received_at = None
    latest_stored_received_at = _latest_stored_received_at(db, user.id)
    pages_fetched = 0

    try:
        response = gmail_service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=max_results).execute()
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Gmail API request failed") from exc

    messages = response.get("messages", [])
    while True:
        pages_fetched += 1
        for message_meta in messages:
            processed += 1
            message_id = message_meta.get("id")
            if not message_id:
                continue
            gmail_message_ids.append(message_id)

            existing = (
                db.query(EmailMessage)
                .filter(EmailMessage.user_id == user.id, EmailMessage.gmail_message_id == message_id)
                .first()
            )
            if existing:
                duplicates += 1
                continue

            try:
                message = gmail_service.users().messages().get(userId="me", id=message_id, format="full").execute()
            except Exception as exc:
                raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Gmail API request failed") from exc

            payload = message.get("payload") or {}
            headers = {item.get("name", "").lower(): item.get("value") for item in payload.get("headers", []) if item.get("name")}
            plain_body, html_body, attachments = _extract_parts(payload)
            internal_date = message.get("internalDate")
            received_at = (
                datetime.fromtimestamp(int(internal_date) / 1000, tz=timezone.utc)
                if internal_date
                else None
            )
            if latest_gmail_received_at is None and received_at is not None:
                latest_gmail_received_at = received_at

            email_record = EmailMessage(
                user_id=user.id,
                gmail_message_id=message_id,
                gmail_thread_id=message.get("threadId"),
                sender=headers.get("from"),
                recipient=headers.get("to"),
                subject=headers.get("subject"),
                snippet=message.get("snippet"),
                plain_body=plain_body,
                html_body=html_body,
                received_at=received_at,
                has_attachments=bool(attachments),
                attachment_metadata=json.dumps(attachments),
                is_read_from_gmail=bool(message.get("labelIds") and "UNREAD" not in message.get("labelIds", [])),
                is_summarized=False,
                updated_at=datetime.now(timezone.utc),
            )
            db.add(email_record)
            try:
                db.commit()
                inserted += 1
                inserted_email_ids.append(email_record.id)
                inserted_gmail_message_ids.append(message_id)
            except Exception as exc:
                db.rollback()
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database save failure") from exc

        next_page_token = response.get("nextPageToken")
        if not next_page_token or pages_fetched >= max_pages:
            break
        try:
            response = gmail_service.users().messages().list(
                userId="me",
                labelIds=["INBOX"],
                maxResults=max_results,
                pageToken=next_page_token,
            ).execute()
            messages = response.get("messages", [])
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Gmail API request failed") from exc

    if latest_gmail_received_at is None and gmail_message_ids:
        try:
            newest = gmail_service.users().messages().get(userId="me", id=gmail_message_ids[0], format="metadata").execute()
            newest_internal_date = newest.get("internalDate")
            if newest_internal_date:
                latest_gmail_received_at = datetime.fromtimestamp(int(newest_internal_date) / 1000, tz=timezone.utc)
        except Exception:
            latest_gmail_received_at = None

    latest_stored_received_at = _latest_stored_received_at(db, user.id)

    logger.info(
        "Gmail sync user_id=%s gmail_returned=%s first_ids=%s latest_gmail_received_at=%s latest_stored_received_at=%s synced_count=%s skipped_duplicates=%s total_processed=%s max_results=%s max_pages=%s",
        user.id,
        len(gmail_message_ids),
        gmail_message_ids[:5],
        latest_gmail_received_at.isoformat() if latest_gmail_received_at else None,
        latest_stored_received_at.isoformat() if latest_stored_received_at else None,
        inserted,
        duplicates,
        processed,
        max_results,
        max_pages,
    )

    return {
        "synced_count": inserted,
        "skipped_duplicates": duplicates,
        "total_processed": processed,
        "latest_gmail_received_at": latest_gmail_received_at,
        "latest_stored_received_at": latest_stored_received_at,
        "gmail_returned_count": len(gmail_message_ids),
        "inserted_email_ids": inserted_email_ids,
        "inserted_gmail_message_ids": inserted_gmail_message_ids,
    }


def list_user_emails(db: Session, user_id: int, page: int, limit: int) -> tuple[list[EmailMessage], int]:
    query = db.query(EmailMessage).filter(EmailMessage.user_id == user_id)
    total = query.count()
    items = (
        query.order_by(EmailMessage.received_at.desc().nullslast(), EmailMessage.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return items, total


def get_user_email(db: Session, user_id: int, email_id: int) -> EmailMessage:
    email = db.query(EmailMessage).filter(EmailMessage.user_id == user_id, EmailMessage.id == email_id).first()
    if email is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")
    return email


def get_sync_status(db: Session, user_id: int) -> dict[str, object]:
    connection = _get_connection(db, user_id)
    total = db.query(EmailMessage).filter(EmailMessage.user_id == user_id).count()
    last_email = (
        db.query(EmailMessage)
        .filter(EmailMessage.user_id == user_id)
        .order_by(EmailMessage.updated_at.desc(), EmailMessage.id.desc())
        .first()
    )
    return {
        "last_sync_time": last_email.updated_at if last_email else None,
        "total_emails_stored": total,
        "gmail_connected": bool(connection and connection.is_connected),
    }


def email_to_list_item(email: EmailMessage):
    return {
        "id": email.id,
        "gmail_message_id": email.gmail_message_id,
        "gmail_thread_id": email.gmail_thread_id,
        "sender": email.sender,
        "recipient": email.recipient,
        "subject": email.subject,
        "snippet": email.snippet,
        "received_at": email.received_at,
        "has_attachments": email.has_attachments,
        "is_read_from_gmail": email.is_read_from_gmail,
        "is_summarized": email.is_summarized,
        "created_at": email.created_at,
        "updated_at": email.updated_at,
    }


def email_to_detail(email: EmailMessage):
    attachment_metadata = []
    if email.attachment_metadata:
        try:
            attachment_metadata = json.loads(email.attachment_metadata)
        except Exception:
            attachment_metadata = []
    item = email_to_list_item(email)
    item.update(
        {
            "plain_body": email.plain_body,
            "html_body": email.html_body,
            "attachment_metadata": attachment_metadata,
        }
    )
    return item
