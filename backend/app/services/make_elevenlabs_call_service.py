from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models.email_summary import EmailSummary
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.user import User

logger = logging.getLogger(__name__)

EMAIL_ADDRESS_RE = re.compile(r"(?<![\w.-])[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
FORWARDED_BLOCK_RE = re.compile(r"(?is)-{3,}\s*forwarded message\s*-{3,}.*?(?=\n\s*\n|\Z)")
HEADER_LINE_RE = re.compile(r"(?im)^\s*(from|date|subject|to|cc|bcc|sent):\s*.*$")


@dataclass(slots=True)
class CleanMailSummaryItem:
    number: int
    sender_name: str
    subject: str
    short_summary: str
    detailed_summary: str
    priority: str
    action_required: bool


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _sanitize_text(text: str | None, *, max_chars: int = 320) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    cleaned = FORWARDED_BLOCK_RE.sub(" ", cleaned)
    cleaned = HEADER_LINE_RE.sub(" ", cleaned)
    cleaned = URL_RE.sub(" ", cleaned)
    cleaned = EMAIL_ADDRESS_RE.sub("the sender", cleaned)
    cleaned = cleaned.replace("<", " ").replace(">", " ")
    cleaned = re.sub(r"-{4,}", " ", cleaned)
    cleaned = _normalize_whitespace(cleaned)
    if not cleaned:
        return ""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]
    if sentences:
        cleaned = " ".join(sentences[:2]).strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rsplit(" ", 1)[0].rstrip(".,;: ")
    return cleaned.strip()


def _sender_name(sender: str | None) -> str:
    raw = (sender or "").strip()
    if not raw:
        return "Unknown sender"
    if "<" in raw and ">" in raw:
        display = raw.split("<", 1)[0].strip()
        if display:
            return _sanitize_text(display, max_chars=120) or "Unknown sender"
    if EMAIL_ADDRESS_RE.search(raw):
        return "Unknown sender"
    return _sanitize_text(raw, max_chars=120) or "Unknown sender"


def _subject(subject: str | None) -> str:
    text = (subject or "No subject").strip() or "No subject"
    for prefix in ("re:", "fwd:"):
        if text.lower().startswith(prefix):
            text = text[len(prefix):].strip()
    return _sanitize_text(text, max_chars=180) or "No subject"


def _summary_text(summary: EmailSummary | None) -> CleanMailSummaryItem:
    subject = _subject(summary.subject if summary else None)
    short_summary = _sanitize_text(summary.short_summary if summary else None, max_chars=240)
    detailed_summary = _sanitize_text(summary.detailed_summary if summary else None, max_chars=320)
    action_required = _sanitize_text(summary.action_required_text if summary else None, max_chars=160)
    action_needed = bool(action_required and action_required.lower() not in {"no clear action requested.", "no clear action requested"})
    if not short_summary:
        short_summary = f"Email received about {subject}. It may need review based on the subject and sender."
    if not detailed_summary:
        detailed_summary = short_summary
    return CleanMailSummaryItem(
        number=0,
        sender_name=_sender_name(summary.sender if summary else None),
        subject=subject,
        short_summary=short_summary,
        detailed_summary=detailed_summary,
        priority="high" if action_needed else "normal",
        action_required=action_needed,
    )


def _resolve_summaries(db: Session, call_log: MailSummaryCallLog, summaries: Iterable[EmailSummary] | None = None) -> list[EmailSummary]:
    if summaries is not None:
        return list(summaries)
    summary_ids: list[int] = []
    raw_ids = call_log.delivered_summary_ids or ""
    if raw_ids.strip():
        try:
            parsed = json.loads(raw_ids)
            if isinstance(parsed, list):
                summary_ids = [int(item) for item in parsed if str(item).strip().isdigit()]
        except Exception:
            summary_ids = []
    if summary_ids:
        return (
            db.query(EmailSummary)
            .filter(
                EmailSummary.user_id == call_log.user_id,
                EmailSummary.id.in_(summary_ids),
            )
            .all()
        )
    return (
        db.query(EmailSummary)
        .filter(
            EmailSummary.user_id == call_log.user_id,
            EmailSummary.mail_call_log_id == call_log.id,
        )
        .order_by(EmailSummary.id.asc())
        .all()
    )


def _build_payload(user: User, call_log: MailSummaryCallLog, summaries: list[EmailSummary]) -> dict[str, Any]:
    clean_items: list[dict[str, Any]] = []
    for index, summary in enumerate(summaries, start=1):
        item = _summary_text(summary)
        item.number = index
        clean_items.append(asdict(item))
    preferred_language = (user.preferred_language or settings.default_summary_language or "tanglish").strip() or "tanglish"
    return {
        "user_name": (user.name or user.email or "User").strip(),
        "preferred_language": preferred_language,
        "call_purpose": "daily_mail_summary",
        "total_emails": len(clean_items),
        "call_id": call_log.id,
        "emails_json": json.dumps(clean_items, ensure_ascii=False),
    }


def send_mail_summary_call_to_make(
    db: Session,
    user: User,
    call_log: MailSummaryCallLog,
    summaries: Iterable[EmailSummary] | None = None,
) -> dict[str, Any]:
    if not settings.make_elevenlabs_webhook_url:
        logger.warning(
            "Make ElevenLabs webhook URL is missing; cannot send mail summary call for call_id=%s user_id=%s",
            call_log.id,
            user.id,
        )
        return {
            "success": False,
            "provider": "make",
            "status": "missing_config",
            "message": "Make ElevenLabs webhook URL is not configured.",
            "payload": None,
        }

    resolved_summaries = _resolve_summaries(db, call_log, summaries)
    payload = _build_payload(user, call_log, resolved_summaries)
    try:
        response = httpx.post(settings.make_elevenlabs_webhook_url, json=payload, timeout=20.0)
        response.raise_for_status()
        logger.info(
            "Sent mail summary call to Make for call_id=%s user_id=%s summary_count=%s",
            call_log.id,
            user.id,
            payload["total_emails"],
        )
        return {
            "success": True,
            "provider": "make",
            "status": "queued",
            "message": "Mail summary call sent to Make successfully.",
            "payload": payload,
        }
    except Exception as exc:
        logger.warning(
            "Make ElevenLabs webhook request failed for call_id=%s user_id=%s error=%s: %s",
            call_log.id,
            user.id,
            type(exc).__name__,
            exc,
        )
        return {
            "success": False,
            "provider": "make",
            "status": "failed",
            "message": "Mail summary call could not be sent to Make.",
            "payload": payload,
        }
