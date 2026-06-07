from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from urllib import error, request
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.email_message import EmailMessage
from app.models.email_summary import EmailSummary
from app.models.user import User


def _clean_text(value: str | None, fallback: str = "") -> str:
    return (value or fallback).replace("\x00", " ").strip()


def _body_for_summary(email: EmailMessage) -> str:
    body = _clean_text(email.plain_body) or _clean_text(email.html_body)
    if not body:
        return "Email body was empty."
    return body[:4000]


def _first_safe_portion(email: EmailMessage) -> str:
    body = _body_for_summary(email)
    return body[:300].strip() or "Email body was empty."


def _attachment_note(email: EmailMessage) -> str:
    if not email.attachment_metadata:
        return "No attachments mentioned."
    try:
        attachments = json.loads(email.attachment_metadata)
    except json.JSONDecodeError:
        attachments = []
    if not attachments:
        return "No attachments mentioned."
    names = [item.get("filename") or item.get("mime_type") or "Unnamed attachment" for item in attachments[:5]]
    return f"Attachment metadata present: {', '.join(names)}."


def _extract_action_required(email: EmailMessage) -> str:
    body = _body_for_summary(email).lower()
    cues = ["please", "kindly", "action required", "reply", "respond", "confirm", "complete", "review", "apply", "connect"]
    if any(cue in body for cue in cues):
        return "The email appears to request a follow-up or action. Review the detailed summary."
    return "No clear action requested."


def _mock_summary(email: EmailMessage) -> dict[str, str]:
    sender = email.sender or "Unknown sender"
    subject = email.subject or "No subject"
    return {
        "short_summary": f"This email is from {sender} about {subject}.",
        "detailed_summary": f"This email contains the following content: {_first_safe_portion(email)}",
        "action_required_text": _extract_action_required(email),
        "attachment_note": _attachment_note(email),
    }


def _openai_summary(email: EmailMessage) -> dict[str, str]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is missing")

    prompt = {
        "sender": email.sender or "Unknown sender",
        "subject": email.subject or "No subject",
        "body": _body_for_summary(email),
        "attachment_note": _attachment_note(email),
    }
    payload = {
        "model": settings.openai_model,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Summarize this email clearly. Do not invent facts. Do not mark it important or unimportant. "
                    "Mention sender and subject. Keep short summary suitable for phone call. Detailed summary should explain "
                    "the content in simple language. If action is requested, describe it neutrally as action_required_text. "
                    "If no clear action is requested, say 'No clear action requested.' Return JSON with keys "
                    "short_summary, detailed_summary, action_required_text, attachment_note."
                ),
            },
            {"role": "user", "content": json.dumps(prompt)},
        ],
    }
    req = request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.openai_api_key}",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=60) as response:
            data = json.loads(response.read().decode())
    except error.HTTPError as exc:
        raise RuntimeError(f"LLM API failure: {exc.reason}") from exc
    except Exception as exc:
        raise RuntimeError("LLM API failure") from exc

    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    parsed["attachment_note"] = parsed.get("attachment_note") or _attachment_note(email)
    parsed["action_required_text"] = parsed.get("action_required_text") or "No clear action requested."
    return parsed


def _generate_summary(email: EmailMessage) -> dict[str, str]:
    provider = settings.llm_provider.lower().strip()
    if provider == "openai":
        return _openai_summary(email)
    return _mock_summary(email)


def generate_all_summaries(db: Session, user: User) -> dict[str, int]:
    emails = db.query(EmailMessage).filter(EmailMessage.user_id == user.id).all()
    if not emails:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No emails found")
    email_ids = [email.id for email in emails]
    return summarize_email_ids(db, user, email_ids)


def summarize_email_ids(db: Session, user: User, email_ids: list[int]) -> dict[str, int]:
    if not email_ids:
        return {
            "processed_count": 0,
            "success_count": 0,
            "failed_count": 0,
            "already_summarized_count": 0,
        }

    emails = (
        db.query(EmailMessage)
        .filter(EmailMessage.user_id == user.id, EmailMessage.id.in_(email_ids))
        .order_by(EmailMessage.created_at.asc(), EmailMessage.id.asc())
        .all()
    )
    already_summarized = sum(1 for email in emails if email.is_summarized)
    unsummarized = [email for email in emails if not email.is_summarized]

    if not unsummarized:
        return {
            "processed_count": 0,
            "success_count": 0,
            "failed_count": 0,
            "already_summarized_count": already_summarized,
        }

    success_count = 0
    failed_count = 0
    for email in unsummarized:
        summary = db.query(EmailSummary).filter(EmailSummary.email_message_id == email.id).first()
        if summary is None:
            summary = EmailSummary(
                user_id=user.id,
                email_message_id=email.id,
                sender=email.sender,
                subject=email.subject,
                summary_status="pending",
                updated_at=datetime.now(timezone.utc),
            )
        try:
            generated = _generate_summary(email)
            summary.sender = email.sender
            summary.subject = email.subject
            summary.short_summary = generated["short_summary"]
            summary.detailed_summary = generated["detailed_summary"]
            summary.action_required_text = generated["action_required_text"]
            summary.attachment_note = generated["attachment_note"]
            summary.summary_status = "completed"
            summary.error_message = None
            summary.updated_at = datetime.now(timezone.utc)
            email.is_summarized = True
            db.add(summary)
            db.add(email)
            db.commit()
            success_count += 1
        except Exception as exc:
            db.rollback()
            summary.summary_status = "failed"
            summary.error_message = str(exc)
            summary.updated_at = datetime.now(timezone.utc)
            db.add(summary)
            db.commit()
            failed_count += 1

    return {
        "processed_count": len(unsummarized),
        "success_count": success_count,
        "failed_count": failed_count,
        "already_summarized_count": already_summarized,
    }


def list_summaries(db: Session, user_id: int, page: int, limit: int) -> list[EmailSummary]:
    return (
        db.query(EmailSummary)
        .filter(EmailSummary.user_id == user_id)
        .order_by(EmailSummary.created_at.desc(), EmailSummary.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )


def get_summary(db: Session, user_id: int, summary_id: int) -> EmailSummary:
    summary = db.query(EmailSummary).filter(EmailSummary.user_id == user_id, EmailSummary.id == summary_id).first()
    if summary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid summary ID")
    return summary


def list_todays_summaries(db: Session, user: User) -> list[EmailSummary]:
    tz_name = user.timezone or "UTC"
    user_tz = ZoneInfo(tz_name)
    start_local = datetime.now(user_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    return (
        db.query(EmailSummary)
        .join(EmailMessage, EmailMessage.id == EmailSummary.email_message_id)
        .filter(
            EmailSummary.user_id == user.id,
            EmailMessage.received_at >= start_utc,
            EmailMessage.received_at < end_utc,
        )
        .order_by(EmailSummary.created_at.desc(), EmailSummary.id.desc())
        .all()
    )


def summary_to_item(summary: EmailSummary) -> dict[str, object]:
    return {
        "id": summary.id,
        "email_message_id": summary.email_message_id,
        "sender": summary.sender,
        "subject": summary.subject,
        "short_summary": summary.short_summary,
        "action_required_text": summary.action_required_text,
        "attachment_note": summary.attachment_note,
        "summary_status": summary.summary_status,
        "error_message": summary.error_message,
        "is_delivered_in_mail_call": summary.is_delivered_in_mail_call,
        "delivered_at": summary.delivered_at,
        "mail_call_log_id": summary.mail_call_log_id,
        "created_at": summary.created_at,
        "updated_at": summary.updated_at,
    }


def summary_to_detail(summary: EmailSummary) -> dict[str, object]:
    data = summary_to_item(summary)
    data["detailed_summary"] = summary.detailed_summary
    return data


def get_summary_counts(db: Session, user_id: int) -> dict[str, int]:
    total_summaries = db.query(EmailSummary).filter(EmailSummary.user_id == user_id).count()
    unsummarized_count = db.query(EmailMessage).filter(EmailMessage.user_id == user_id, EmailMessage.is_summarized.is_(False)).count()
    today = datetime.now(timezone.utc).date()
    generated_today = (
        db.query(EmailSummary)
        .filter(
            EmailSummary.user_id == user_id,
            EmailSummary.created_at >= datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc),
        )
        .count()
    )
    return {
        "total_summaries": total_summaries,
        "unsummarized_count": unsummarized_count,
        "generated_today": generated_today,
    }
