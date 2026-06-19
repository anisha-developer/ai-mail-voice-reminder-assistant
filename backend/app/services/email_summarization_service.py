from __future__ import annotations

import json
import logging
import html
import re
from html.parser import HTMLParser
from email.utils import parseaddr
from datetime import datetime, timedelta, timezone
from urllib import error, request
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.email_message import EmailMessage
from app.models.email_summary import EmailSummary
from app.models.user import User
from app.core.timezone import normalize_timezone_name
from app.services.gemini_email_agent_service import generate_understanding_summary


logger = logging.getLogger(__name__)


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data:
            self._parts.append(data)

    def handle_comment(self, data: str) -> None:
        return

    def get_text(self) -> str:
        return " ".join(part.strip() for part in self._parts if part and part.strip())


def _strip_html_markup(value: str | None) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    lowered = text.lower()
    if "<" not in text and "&" not in text and "doctype" not in lowered and "xmlns" not in lowered:
        return html.unescape(text)
    text = re.sub(r"(?is)<!doctype.*?>", " ", text)
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?is)<head[^>]*>.*?</head>", " ", text)
    parser = _HTMLTextExtractor()
    try:
        parser.feed(text)
        parser.close()
        text = parser.get_text()
    except Exception:
        text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"(?is)xmlns[:=][^\s>]+", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _clean_text(value: str | None, fallback: str = "") -> str:
    return (value or fallback).replace("\x00", " ").strip()


def _summary_language() -> str:
    return (settings.default_summary_language or "english").strip().lower()


def _sender_name(sender: str | None) -> str:
    sender_text = _clean_text(sender)
    if not sender_text:
        return "Unknown sender"
    display_name, email_addr = parseaddr(sender_text)
    if display_name.strip():
        return display_name.strip()
    if "<" in sender_text and ">" in sender_text:
        prefix = sender_text.split("<", 1)[0].strip()
        if prefix:
            return prefix
    if "@" in email_addr:
        return email_addr.strip()
    return "Unknown sender"


def _body_for_summary(email: EmailMessage) -> str:
    body = _strip_html_markup(email.plain_body) or _strip_html_markup(email.html_body)
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


def _tanglish_topic_sentence(email: EmailMessage) -> str:
    text = f"{_clean_text(email.subject)} {_body_for_summary(email)}".lower()
    if any(keyword in text for keyword in ["promotional", "promo", "marketing", "offer", "sale", "discount", "subscribe", "newsletter", "ad ", "advertisement", "deal", "limited time"]):
        return "Idhu promotional/update email madhiri theriyudhu. Important action edhuvum illa; thevai na mattum review pannunga."
    if any(keyword in text for keyword in ["test email", "test mail", "verify", "working correctly", "system is working", "check whether", "checking the email system"]):
        return "Idhu email system proper-a work aagudha nu verify panna anuppuna test email."
    if any(keyword in text for keyword in ["hospital", "appointment", "follow-up", "follow up", "reminder"]):
        return "Idhu hospital appointment or follow-up reminder mail."
    if any(keyword in text for keyword in ["notification", "update", "alert"]):
        return "Idhu notification or update mail."
    if any(keyword in text for keyword in ["invoice", "payment", "bill", "receipt"]):
        return "Idhu payment or invoice related mail."
    if any(keyword in text for keyword in ["job", "interview", "application", "career"]):
        return "Idhu job or application related mail."
    if any(keyword in text for keyword in ["reply", "respond", "confirm"]):
        return "Idharku reply or confirmation thevai irukkalaam."
    if any(keyword in text for keyword in ["meeting", "call", "zoom"]):
        return "Idhu meeting related mail."
    return "Idhu review panna vendiya important mail."


def _tanglish_action_sentence(email: EmailMessage, generated_action: str | None = None) -> str:
    action = _clean_text(generated_action).lower()
    body = _body_for_summary(email).lower()
    if "no clear action" in action or action in {"unclear", "none", "no action needed."}:
        if any(keyword in body for keyword in ["please ignore", "ignore this message", "just testing"]):
            return "Idha ignore pannalam; action thevai illa."
        return "Action thevai illa."
    if any(keyword in action for keyword in ["reply", "respond"]):
        return "Idharku reply panna vendiyadhu irukku."
    if any(keyword in action for keyword in ["review", "check", "verify"]):
        return "Idha review pannitu thevai na action edunga."
    return "Idha review pannitu thevai na respond pannunga."


def _tanglish_summary_payload(
    email: EmailMessage,
    *,
    action_required_text: str | None = None,
    deadline_or_date: str | None = None,
    suggested_reminder: str | None = None,
) -> dict[str, str]:
    subject = _clean_text(email.subject) or "No subject"
    topic_sentence = _tanglish_topic_sentence(email)
    action_sentence = _tanglish_action_sentence(email, action_required_text)
    deadline_sentence = ""
    deadline_text = _clean_text(deadline_or_date)
    if deadline_text:
        deadline_sentence = f"Deadline/date {deadline_text} nu irukku."
    reminder_sentence = ""
    reminder_text = _clean_text(suggested_reminder)
    if reminder_text:
        reminder_sentence = f"Reminder-a vechukka {reminder_text} useful-aa irukkum."
    short_summary = f"Indha email {subject} pathi vandhurukku. {topic_sentence} {action_sentence}".strip()
    detailed_summary = " ".join(
        part
        for part in [
            f"Indha email {subject} pathi irukku.",
            topic_sentence,
            action_sentence,
            deadline_sentence,
            reminder_sentence,
        ]
        if part
    ).strip()
    return {
        "short_summary": short_summary,
        "detailed_summary": detailed_summary,
        "action_required_text": "No clear action requested." if action_sentence == "Action thevai illa." else action_sentence,
        "attachment_note": _attachment_note(email),
    }


def _mock_summary(email: EmailMessage) -> dict[str, str]:
    summary = _tanglish_summary_payload(
        email,
        action_required_text=_extract_action_required(email),
        deadline_or_date=None,
        suggested_reminder=None,
    )
    if _summary_language() not in {"tamil", "tanglish"}:
        sender = _sender_name(email.sender)
        subject = email.subject or "No subject"
        body = _first_safe_portion(email)
        summary_hint = subject.lower()
        if any(keyword in summary_hint for keyword in ["hospital", "appointment", "follow-up", "follow up", "reminder"]):
            short_summary = f"{subject} related reminder mail vandhurukku. Review panna vendiya follow-up mail."
            detailed_summary = f"{subject} related reminder mail vandhurukku. Idhu appointment or follow-up related mail."
        elif any(keyword in summary_hint for keyword in ["quora", "notification", "update"]):
            short_summary = f"{subject} related notification mail vandhurukku. Review panna podhum."
            detailed_summary = f"{subject} related notification mail vandhurukku. Idhu account activity or content update related mail."
        else:
            short_summary = f"Email received about {subject}. It may need review based on the subject and sender."
            detailed_summary = f"Email received about {subject}. It looks like a message from {sender}."
        return {
            "short_summary": short_summary,
            "detailed_summary": detailed_summary,
            "action_required_text": _extract_action_required(email),
            "attachment_note": _attachment_note(email),
        }
    return summary


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


def _legacy_generate_summary(email: EmailMessage) -> dict[str, str]:
    provider = settings.llm_provider.lower().strip()
    if provider == "openai":
        return _openai_summary(email)
    return _mock_summary(email)


def _gemini_summary(email: EmailMessage) -> dict[str, str]:
    generated = generate_understanding_summary(
        subject=email.subject,
        sender=email.sender,
        body=_body_for_summary(email),
        preferred_language=settings.default_summary_language,
    )
    important_points = generated.get("important_points") or []
    if isinstance(important_points, list):
        important_points_text = "; ".join(str(item).strip() for item in important_points if str(item).strip())
    else:
        important_points_text = str(important_points).strip()
    detail_parts = [str(generated.get("short_summary") or "").strip()]
    if important_points_text:
        detail_parts.append(f"Important points: {important_points_text}")
    action_required = str(generated.get("action_required") or "").strip()
    if action_required and action_required.lower() not in {"unclear", "none"}:
        detail_parts.append(f"Action required: {action_required}")
    deadline_or_date = str(generated.get("deadline_or_date") or "").strip()
    if deadline_or_date:
        detail_parts.append(f"Deadline or date: {deadline_or_date}")
    suggested_reminder = str(generated.get("suggested_reminder") or "").strip()
    if suggested_reminder:
        detail_parts.append(f"Suggested reminder: {suggested_reminder}")
    detailed_summary = " ".join(part for part in detail_parts if part).strip()
    if not detailed_summary:
        detailed_summary = _first_safe_portion(email)
    language = _summary_language()
    short_summary = str(generated.get("short_summary") or "").strip()
    if language in {"tamil", "tanglish"}:
        tanglish = _tanglish_summary_payload(
            email,
            action_required_text=str(generated.get("action_required") or "").strip(),
            deadline_or_date=str(generated.get("deadline_or_date") or "").strip(),
            suggested_reminder=str(generated.get("suggested_reminder") or "").strip(),
        )
        short_summary = tanglish["short_summary"]
        detailed_summary = tanglish["detailed_summary"]
        action_required_text = tanglish["action_required_text"]
        attachment_note = tanglish["attachment_note"]
    else:
        if short_summary and short_summary.lower().startswith("this email is from ") and email.subject:
            short_summary = f"Email received about {email.subject}. It may need review based on the subject and sender."
        action_required_text = "No clear action requested." if not action_required or action_required.lower() == "unclear" else action_required
        attachment_note = _attachment_note(email)
    return {
        "short_summary": short_summary or _mock_summary(email)["short_summary"],
        "detailed_summary": detailed_summary,
        "action_required_text": action_required_text,
        "attachment_note": attachment_note,
    }


def _generate_summary(email: EmailMessage) -> dict[str, str]:
    provider = settings.email_summary_provider.lower().strip()
    if provider == "gemini" and settings.gemini_api_key:
        try:
            return _gemini_summary(email)
        except Exception:
            logger.warning(
                "Gemini summary fallback used for email_id=%s subject=%s; using legacy summary",
                getattr(email, "id", None),
                (email.subject or "No subject")[:120],
            )
            return _legacy_generate_summary(email)
    if provider == "gemini" and not settings.gemini_api_key:
        logger.warning(
            "Gemini summary skipped because GEMINI_API_KEY is missing for email_id=%s subject=%s",
            getattr(email, "id", None),
            (email.subject or "No subject")[:120],
        )
    return _legacy_generate_summary(email)


def generate_all_summaries(db: Session, user: User) -> dict[str, int]:
    emails = db.query(EmailMessage).filter(EmailMessage.user_id == user.id, EmailMessage.is_in_inbox.is_(True)).all()
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
    tz_name = normalize_timezone_name(user.timezone, "UTC")
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
            EmailSummary.summary_status == "completed",
            EmailMessage.is_in_inbox.is_(True),
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
    user = db.query(User).filter(User.id == user_id).first()
    tz_name = normalize_timezone_name(user.timezone if user else "UTC", "UTC")
    user_tz = ZoneInfo(tz_name)
    start_local = datetime.now(user_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    total_summaries = db.query(EmailSummary).filter(EmailSummary.user_id == user_id).count()
    unsummarized_count = (
        db.query(EmailMessage)
        .filter(EmailMessage.user_id == user_id, EmailMessage.is_in_inbox.is_(True), EmailMessage.is_summarized.is_(False))
        .count()
    )
    generated_today = (
        db.query(EmailSummary)
        .join(EmailMessage, EmailMessage.id == EmailSummary.email_message_id)
        .filter(
            EmailSummary.user_id == user_id,
            EmailSummary.summary_status == "completed",
            EmailMessage.is_in_inbox.is_(True),
            EmailMessage.received_at.is_not(None),
            EmailMessage.received_at >= start_utc,
            EmailMessage.received_at < end_utc,
        )
        .count()
    )
    return {
        "total_summaries": total_summaries,
        "unsummarized_count": unsummarized_count,
        "generated_today": generated_today,
    }
