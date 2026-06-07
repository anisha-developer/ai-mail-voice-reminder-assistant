from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.database.session import SessionLocal
from app.models.email_message import EmailMessage
from app.models.gmail_connection import GmailConnection
from app.models.user import User
from app.services.email_summarization_service import summarize_email_ids
from app.services.gmail_email_service import sync_user_emails

logger = logging.getLogger(__name__)


def _connected_gmail_query(db: Session):
    return (
        db.query(GmailConnection)
        .join(User, User.id == GmailConnection.user_id)
        .filter(
            GmailConnection.is_connected.is_(True),
            GmailConnection.refresh_token_encrypted.is_not(None),
        )
        .order_by(GmailConnection.updated_at.asc(), GmailConnection.id.asc())
    )


def run_auto_email_sync_once() -> None:
    db = SessionLocal()
    try:
        connections = _connected_gmail_query(db).limit(settings.auto_email_sync_batch_users).all()
        for connection in connections:
            try:
                user = db.query(User).filter(User.id == connection.user_id).first()
                if user is None:
                    continue
                result = sync_user_emails(
                    db,
                    user,
                    max_results=settings.auto_email_sync_max_results,
                    max_pages=settings.auto_email_sync_max_pages,
                )
                connection.last_auto_sync_at = datetime.now(timezone.utc)
                connection.last_auto_sync_status = "success"
                connection.last_auto_sync_error = None
                connection.last_auto_sync_inserted_count = int(result.get("synced_count", 0))
                db.add(connection)
                db.commit()

                logger.info(
                    "Auto email sync success user_id=%s gmail_email=%s synced_count=%s skipped_duplicates=%s total_processed=%s latest_gmail_received_at=%s latest_stored_received_at=%s",
                    user.id,
                    connection.gmail_email,
                    result.get("synced_count"),
                    result.get("skipped_duplicates"),
                    result.get("total_processed"),
                    result.get("latest_gmail_received_at"),
                    result.get("latest_stored_received_at"),
                )

                if settings.auto_summarize_after_sync and int(result.get("synced_count", 0)) > 0:
                    inserted_email_ids = [int(email_id) for email_id in result.get("inserted_email_ids", []) if email_id is not None]
                    if not inserted_email_ids:
                        inserted_email_ids = [
                            email.id
                            for email in db.query(EmailMessage)
                            .filter(EmailMessage.user_id == user.id, EmailMessage.is_summarized.is_(False))
                            .order_by(EmailMessage.created_at.asc(), EmailMessage.id.asc())
                            .all()
                        ]
                    summary_started_at = datetime.now(timezone.utc)
                    try:
                        summary_result = summarize_email_ids(db, user, inserted_email_ids)
                        connection.last_auto_summary_at = summary_started_at
                        connection.last_auto_summary_status = (
                            "success"
                            if summary_result.get("failed_count", 0) == 0
                            else "partial_failed"
                        )
                        connection.last_auto_summary_error = None
                        connection.last_auto_summary_success_count = int(summary_result.get("success_count", 0))
                        connection.last_auto_summary_failed_count = int(summary_result.get("failed_count", 0))
                        db.add(connection)
                        db.commit()
                        logger.info(
                            "Auto summary success user_id=%s gmail_email=%s success_count=%s failed_count=%s inserted_email_ids=%s",
                            user.id,
                            connection.gmail_email,
                            summary_result.get("success_count"),
                            summary_result.get("failed_count"),
                            inserted_email_ids,
                        )
                    except Exception as exc:
                        db.rollback()
                        connection.last_auto_summary_at = summary_started_at
                        connection.last_auto_summary_status = "failed"
                        connection.last_auto_summary_error = str(exc)
                        connection.last_auto_summary_success_count = 0
                        connection.last_auto_summary_failed_count = len(inserted_email_ids)
                        db.add(connection)
                        db.commit()
                        logger.error(
                            "Auto summary failed user_id=%s gmail_email=%s error=%s inserted_email_ids=%s",
                            user.id,
                            connection.gmail_email,
                            str(exc),
                            inserted_email_ids,
                        )
                elif settings.auto_summarize_after_sync and int(result.get("synced_count", 0)) <= 0:
                    connection.last_auto_summary_at = datetime.now(timezone.utc)
                    connection.last_auto_summary_status = "success"
                    connection.last_auto_summary_error = None
                    connection.last_auto_summary_success_count = 0
                    connection.last_auto_summary_failed_count = 0
                    db.add(connection)
                    db.commit()
                else:
                    connection.last_auto_summary_at = datetime.now(timezone.utc)
                    connection.last_auto_summary_status = "disabled"
                    connection.last_auto_summary_error = None
                    connection.last_auto_summary_success_count = 0
                    connection.last_auto_summary_failed_count = 0
                    db.add(connection)
                    db.commit()
            except Exception as exc:
                db.rollback()
                connection.last_auto_sync_at = datetime.now(timezone.utc)
                connection.last_auto_sync_status = "failed"
                connection.last_auto_sync_error = str(exc)
                connection.last_auto_sync_inserted_count = 0
                db.add(connection)
                db.commit()
                logger.error(
                    "Auto email sync failed user_id=%s gmail_email=%s error=%s",
                    connection.user_id,
                    connection.gmail_email,
                    str(exc),
                )
    finally:
        db.close()


def get_auto_sync_status(db: Session, user: User) -> dict[str, object]:
    connection = (
        db.query(GmailConnection)
        .filter(GmailConnection.user_id == user.id, GmailConnection.is_connected.is_(True))
        .first()
    )
    unsummarized_count = (
        db.query(EmailMessage)
        .filter(EmailMessage.user_id == user.id, EmailMessage.is_summarized.is_(False))
        .count()
    )
    return {
        "auto_sync_enabled": settings.auto_email_sync_enabled,
        "interval_minutes": settings.auto_email_sync_interval_minutes,
        "last_auto_sync_at": connection.last_auto_sync_at if connection else None,
        "last_auto_sync_status": connection.last_auto_sync_status if connection else None,
        "last_auto_sync_error": connection.last_auto_sync_error if connection else None,
        "last_auto_sync_inserted_count": (connection.last_auto_sync_inserted_count if connection and connection.last_auto_sync_inserted_count is not None else 0),
        "last_auto_summary_at": connection.last_auto_summary_at if connection else None,
        "last_auto_summary_status": connection.last_auto_summary_status if connection else None,
        "last_auto_summary_error": connection.last_auto_summary_error if connection else None,
        "last_auto_summary_success_count": (connection.last_auto_summary_success_count if connection and connection.last_auto_summary_success_count is not None else 0),
        "last_auto_summary_failed_count": (connection.last_auto_summary_failed_count if connection and connection.last_auto_summary_failed_count is not None else 0),
        "gmail_connected": bool(connection and connection.is_connected),
        "unsummarized_email_count": unsummarized_count,
        "auto_summarize_after_sync": settings.auto_summarize_after_sync,
    }
