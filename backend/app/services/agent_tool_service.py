from __future__ import annotations

from email.utils import parseaddr
from datetime import date, datetime, time, timedelta, timezone
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.models.email_message import EmailMessage
from app.models.email_reply_action import EmailReplyAction
from app.models.email_summary import EmailSummary
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.user import User
from app.models.voice_call_interaction import VoiceCallInteraction
from app.services.email_summarization_service import summary_to_detail
from app.services.gmail_oauth_service import get_connection_credentials
from app.services.mail_summary_call_service import list_pending_today_summaries, list_todays_summaries
from app.services.recurring_reminder_service import create_recurring_rule
from app.services.reminder_service import create_reminder
from app.services.voice_reminder_service import parse_reminder_datetime


def _user_timezone(user: User) -> str:
    return (user.timezone or "UTC").strip() or "UTC"


def _get_user(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def _reference_summaries(db: Session, user: User) -> list[EmailSummary]:
    pending = list_pending_today_summaries(db, user)
    if pending:
        return pending
    return list_todays_summaries(db, user)


def _format_summary_item(reference: int, summary: EmailSummary) -> dict[str, Any]:
    return {
        "reference": reference,
        "email_summary_id": summary.id,
        "email_message_id": summary.email_message_id,
        "sender": summary.sender,
        "subject": summary.subject,
        "short_summary": summary.short_summary,
        "action_required": summary.action_required_text,
    }


def _summary_detail_payload(reference: int, summary: EmailSummary) -> dict[str, Any]:
    payload = summary_to_detail(summary)
    return {
        "reference": reference,
        "sender": payload.get("sender"),
        "subject": payload.get("subject"),
        "short_summary": payload.get("short_summary"),
        "detailed_summary": payload.get("detailed_summary"),
        "action_required": payload.get("action_required_text"),
        "attachment_note": payload.get("attachment_note"),
    }


def _spoken_detail_summary_text(summary: EmailSummary) -> str:
    subject = _spoken_subject(summary.subject)
    text = (summary.detailed_summary or summary.short_summary or summary.action_required_text or "").strip()
    if not text:
        return f"This email is about {subject}."
    cleaned = text
    for prefix in ("re:", "fwd:"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    if cleaned and cleaned != text:
        text = cleaned
    if text and text.lower().startswith("this email is from "):
        return f"This email is about {subject}."
    if not text.endswith("."):
        text = f"{text}."
    return text


def build_email_detail_voice_message(summary: EmailSummary) -> str:
    sender = _spoken_sender_name(summary.sender)
    subject = _spoken_subject(summary.subject)
    detail_summary = _spoken_detail_summary_text(summary)
    action_required = (summary.action_required_text or "").strip()
    action_text = " No clear action is requested."
    if action_required:
        action_text = f" Action required: {action_required}"
    return f"This email is from {sender} about {subject}. Summary: {detail_summary}{action_text}".strip()


def _spoken_sender_name(sender: str | None) -> str:
    raw = (sender or "").strip()
    if not raw:
        return "Unknown sender"
    display_name, email_addr = parseaddr(raw)
    if display_name.strip():
        return display_name.strip()
    if "@" in email_addr:
        return email_addr.strip()
    if "<" in raw and ">" in raw:
        return raw.split("<", 1)[0].strip() or raw
    return raw


def _spoken_subject(subject: str | None) -> str:
    text = (subject or "No subject").strip() or "No subject"
    for prefix in ("re:", "fwd:"):
        if text.lower().startswith(prefix):
            text = text[len(prefix):].strip()
    return text or "No subject"


def _spoken_summary_text(summary: EmailSummary, subject: str) -> str:
    text = (summary.short_summary or summary.detailed_summary or summary.action_required_text or "").strip()
    if not text:
        return f"This email is about {subject}."
    cleaned = text
    for prefix in ("re:", "fwd:"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    if cleaned and cleaned != text:
        text = cleaned
    if text and text.lower().startswith("this email is from "):
        return f"This email is about {subject}."
    if not text.endswith("."):
        text = f"{text}."
    return text


def _summary_voice_snippet(summary: EmailSummary, reference: int) -> str:
    sender = _spoken_sender_name(summary.sender)
    subject = _spoken_subject(summary.subject)
    summary_text = _spoken_summary_text(summary, subject)
    return f"Email {reference} is from {sender} about {subject}. Summary: {summary_text}"


def build_today_summaries_voice_message(summaries: list[EmailSummary]) -> str:
    count = len(summaries)
    if count == 0:
        return "You do not have any summarized emails for today."
    if count > 3:
        snippets = " ".join(_summary_voice_snippet(summary, index) for index, summary in enumerate(summaries[:3], start=1))
        return f"Today you have {count} summarized emails. I will read the first 3. {snippets}"
    snippets = " ".join(_summary_voice_snippet(summary, index) for index, summary in enumerate(summaries, start=1))
    return f"Today you have {count} summarized email{'s' if count != 1 else ''}. {snippets}"


def _summary_by_reference(db: Session, user: User, reference: int) -> tuple[int, EmailSummary] | None:
    summaries = _reference_summaries(db, user)
    if reference < 1 or reference > len(summaries):
        return None
    return reference, summaries[reference - 1]


def _summary_lookup(db: Session, user: User, request) -> tuple[int, EmailSummary] | None:
    if request.email_reference is not None:
        return _summary_by_reference(db, user, request.email_reference)
    if request.email_summary_id is not None:
        summary = db.query(EmailSummary).filter(EmailSummary.user_id == user.id, EmailSummary.id == request.email_summary_id).first()
        if summary is None:
            return None
        return 0, summary
    if request.email_message_id is not None:
        summary = db.query(EmailSummary).filter(EmailSummary.user_id == user.id, EmailSummary.email_message_id == request.email_message_id).first()
        if summary is None:
            return None
        return 0, summary
    return None


def get_today_summaries(db: Session, user: User, request) -> dict[str, Any]:
    summaries = _reference_summaries(db, user)
    message = build_today_summaries_voice_message(summaries)
    if not summaries:
        return {"summaries": [], "count": 0, "message": message}
    items = [_format_summary_item(index, summary) for index, summary in enumerate(summaries, start=1)]
    return {"summaries": items, "count": len(items), "message": message}


def get_email_detail(db: Session, user: User, request) -> dict[str, Any]:
    resolved = _summary_lookup(db, user, request)
    if resolved is None:
        return {
            "success": False,
            "message": "I could not find that email summary. Please ask for today's summaries again and choose one from the list.",
            "data": {"email": None},
        }
    reference, summary = resolved
    detail = _summary_detail_payload(reference or 1, summary)
    return {
        "success": True,
        "message": build_email_detail_voice_message(summary),
        "data": {"email": detail},
    }


def search_email(db: Session, user: User, request) -> dict[str, Any]:
    query = (request.query or "").strip().lower()
    if not query:
        return {"matches": []}
    summaries = db.query(EmailSummary).filter(EmailSummary.user_id == user.id).order_by(EmailSummary.id.desc()).all()
    scored: list[tuple[int, EmailSummary]] = []
    for summary in summaries:
        fields = " ".join(
            part
            for part in [
                summary.sender or "",
                summary.subject or "",
                summary.short_summary or "",
                summary.detailed_summary or "",
                summary.action_required_text or "",
            ]
        ).lower()
        score = sum(1 for token in query.split() if token and token in fields)
        if score:
            scored.append((score, summary))
    scored.sort(key=lambda item: (item[0], item[1].id), reverse=True)
    matches = []
    for index, (_, summary) in enumerate(scored[:5], start=1):
        matches.append(_format_summary_item(index, summary))
    return {"matches": matches}


def _parse_reminder_time(user: User, request) -> tuple[datetime | None, str | None]:
    tz_name = (request.timezone or user.timezone or "UTC").strip() or "UTC"
    if request.reminder_at:
        try:
            parsed = datetime.fromisoformat(request.reminder_at)
        except ValueError:
            return None, "Invalid reminder_at value"
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc), None
    if not request.reminder_time_text:
        return None, "Please provide a reminder time."
    parsed = parse_reminder_datetime(request.reminder_time_text, tz_name)
    if parsed is None:
        return None, "I could not understand the reminder time. Please say a clearer time like tomorrow at 9 AM."
    return parsed.astimezone(timezone.utc), None


def _linked_email_note(summary: EmailSummary | None, reference: int | None) -> str | None:
    if summary is None and reference is None:
        return None
    sender = summary.sender if summary and summary.sender else "Unknown sender"
    subject = summary.subject if summary and summary.subject else "No subject"
    ref_text = f"email reference {reference}" if reference is not None else "selected email"
    return f"Linked to {ref_text}: {sender} / {subject}"


def create_reminder_tool(db: Session, user: User, request) -> dict[str, Any]:
    if not request.title or not request.title.strip():
        return {"success": False, "message": "Please provide a reminder title.", "data": {}}
    reminder_at, error = _parse_reminder_time(user, request)
    if error:
        return {"success": False, "message": error, "data": {}}
    if reminder_at is None:
        return {"success": False, "message": "I could not understand the reminder time. Please say a clearer time like tomorrow at 9 AM.", "data": {}}
    if reminder_at <= datetime.now(timezone.utc):
        return {"success": False, "message": "Reminder time must be in the future.", "data": {}}

    linked_summary = None
    summary_ref = None
    if request.email_reference is not None:
        resolved = _summary_by_reference(db, user, request.email_reference)
        if resolved is None:
            return {"success": False, "message": "I could not find that email. Please say email one, email two, or describe the sender.", "data": {}}
        summary_ref, linked_summary = resolved
    elif request.email_summary_id is not None:
        linked_summary = db.query(EmailSummary).filter(EmailSummary.user_id == user.id, EmailSummary.id == request.email_summary_id).first()
        if linked_summary is None:
            return {"success": False, "message": "I could not find that email. Please say email one, email two, or describe the sender.", "data": {}}
    elif request.email_message_id is not None:
        linked_summary = db.query(EmailSummary).filter(EmailSummary.user_id == user.id, EmailSummary.email_message_id == request.email_message_id).first()
        if linked_summary is None:
            return {"success": False, "message": "I could not find that email. Please say email one, email two, or describe the sender.", "data": {}}

    local_zone = ZoneInfo(_user_timezone(user))
    local_dt = reminder_at.astimezone(local_zone)
    payload = SimpleNamespace(
        title=request.title.strip(),
        notes="\n".join(filter(None, [request.notes.strip() if request.notes else None, _linked_email_note(linked_summary, summary_ref)])),
        reminder_date=local_dt.date().isoformat(),
        reminder_time=local_dt.strftime("%H:%M"),
        timezone=_user_timezone(user),
        phone_number=user.phone_number,
    )
    reminder = create_reminder(db, user, payload)
    return {
        "success": True,
        "message": f"Reminder created for {local_dt.strftime('%A at %I:%M %p')}.",
        "data": {"reminder_id": reminder["id"], "reminder_at": reminder["reminder_at"]},
    }


def create_recurring_reminder_tool(db: Session, user: User, request) -> dict[str, Any]:
    if not request.title or not request.title.strip():
        return {"success": False, "message": "Please provide a recurring reminder title.", "data": {}}
    repeat_type = (request.repeat_type or "").strip().lower()
    if repeat_type not in {"daily", "weekly", "monthly", "weekdays", "custom_days", "custom_interval"}:
        return {"success": False, "message": "Please provide a valid repeat type.", "data": {}}
    if repeat_type in {"daily", "weekdays"} and not request.time_of_day:
        return {"success": False, "message": "Please provide a time of day for this recurring reminder.", "data": {}}
    if repeat_type in {"weekly", "custom_days"} and (not request.days_of_week or not request.time_of_day):
        return {"success": False, "message": "Please provide days of week and a time of day.", "data": {}}
    if repeat_type == "monthly" and (request.day_of_month is None or not request.time_of_day):
        return {"success": False, "message": "Please provide a day of month and a time of day.", "data": {}}
    if repeat_type == "custom_interval" and (request.interval_value is None or not request.interval_unit):
        return {"success": False, "message": "Please provide an interval value and interval unit.", "data": {}}

    payload = SimpleNamespace(
        title=request.title.strip(),
        notes=request.notes,
        timezone=(request.timezone or user.timezone or "UTC").strip() or "UTC",
        repeat_type=repeat_type,
        interval_value=request.interval_value,
        interval_unit=request.interval_unit,
        days_of_week=request.days_of_week,
        day_of_month=request.day_of_month,
        time_of_day=request.time_of_day,
        source_type="agent",
        email_message_id=request.email_message_id,
        email_summary_id=request.email_summary_id,
    )
    result = create_recurring_rule(db, user, payload)
    return {
        "success": True,
        "message": "Recurring reminder created.",
        "data": {"recurring_rule_id": result["id"], "next_occurrence_at": result["next_occurrence_at"]},
    }


def _build_reply_text(request) -> str:
    instruction = (request.reply_instruction or "").strip()
    if not instruction:
        return "Hi."
    if instruction.lower().startswith(("hi", "hello", "dear")):
        return instruction
    return f"Hi, {instruction}"


def _resolve_reply_target(db: Session, user: User, request) -> tuple[EmailSummary | None, EmailMessage | None]:
    resolved = _summary_lookup(db, user, request)
    if resolved is None:
        return None, None
    _, summary = resolved
    message = db.query(EmailMessage).filter(EmailMessage.user_id == user.id, EmailMessage.id == summary.email_message_id).first()
    return summary, message


def draft_email_reply_tool(db: Session, user: User, request) -> dict[str, Any]:
    if not request.reply_instruction or not request.reply_instruction.strip():
        return {"success": False, "message": "Please tell me what the reply should say.", "data": {}}
    summary, message = _resolve_reply_target(db, user, request)
    if summary is None or message is None:
        return {"success": False, "message": "I could not find that email. Please say email one, email two, or describe the sender.", "data": {}}
    draft_text = _build_reply_text(request)
    action = EmailReplyAction(
        user_id=user.id,
        email_message_id=message.id,
        mail_call_log_id=summary.mail_call_log_id,
        voice_reply_session_id=None,
        gmail_message_id=message.gmail_message_id,
        gmail_thread_id=message.gmail_thread_id,
        reply_body=draft_text,
        status="drafted",
        error_message=None,
        created_at=datetime.now(timezone.utc),
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return {
        "success": True,
        "message": "I drafted the reply. Please confirm before sending.",
        "data": {"draft_id": action.id, "draft_text": draft_text},
    }


def _build_raw_message(user: User, to_email: str, subject: str, reply_body: str) -> str:
    from email.message import EmailMessage as SMTPMessage
    import base64

    msg = SMTPMessage()
    msg["To"] = to_email
    msg["From"] = user.email
    normalized_subject = subject.strip()
    if not normalized_subject.lower().startswith("re:"):
        normalized_subject = f"Re: {normalized_subject}"
    msg["Subject"] = normalized_subject
    msg.set_content(reply_body)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def _deliver_reply_from_action(db: Session, user: User, action: EmailReplyAction) -> str:
    if action.email_message_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Draft is missing email context")
    email = db.query(EmailMessage).filter(EmailMessage.user_id == user.id, EmailMessage.id == action.email_message_id).first()
    if email is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")
    creds = get_connection_credentials(db, user.id)
    if creds is None or not getattr(creds, "refresh_token", None):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="I need Gmail send permission before I can send replies. Please reconnect Gmail from the dashboard.")
    if "https://www.googleapis.com/auth/gmail.send" not in (getattr(creds, "scopes", []) or []):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="I need Gmail send permission before I can send replies. Please reconnect Gmail from the dashboard.")
    gmail_service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    raw_message = _build_raw_message(user, email.recipient or user.email, email.subject or "Re: your email", action.reply_body or "")
    sent_message = gmail_service.users().messages().send(userId="me", body={"raw": raw_message, "threadId": action.gmail_thread_id}).execute()
    action.status = "sent"
    action.provider_message_id = sent_message.get("id")
    action.sent_at = datetime.now(timezone.utc)
    db.add(action)
    db.commit()
    return sent_message.get("id") or ""


def send_email_reply_tool(db: Session, user: User, request) -> dict[str, Any]:
    if request.draft_id is None:
        return {"success": False, "message": "Please provide a draft id.", "data": {}}
    action = db.query(EmailReplyAction).filter(EmailReplyAction.user_id == user.id, EmailReplyAction.id == request.draft_id).first()
    if action is None:
        return {"success": False, "message": "I could not find that draft.", "data": {}}
    if action.status != "drafted":
        return {"success": False, "message": "That draft has already been sent or is no longer available.", "data": {}}
    provider_message_id = _deliver_reply_from_action(db, user, action)
    return {"success": True, "message": "Reply sent successfully.", "data": {"draft_id": action.id, "provider_message_id": provider_message_id}}


def log_call_feedback_tool(db: Session, user: User, request) -> dict[str, Any]:
    feedback_text = (request.feedback_text or "").strip()
    if not feedback_text:
        return {"success": False, "message": "Please provide feedback text.", "data": {}}
    call_log = None
    if request.call_id and str(request.call_id).isdigit():
        call_log = db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == int(request.call_id), MailSummaryCallLog.user_id == user.id).first()
    if call_log is None:
        return {"success": True, "message": "Feedback received.", "data": {}}
    next_order = (
        db.query(VoiceCallInteraction.interaction_order)
        .filter(VoiceCallInteraction.user_id == user.id, VoiceCallInteraction.mail_call_log_id == call_log.id)
        .order_by(VoiceCallInteraction.interaction_order.desc())
        .first()
    )
    interaction = VoiceCallInteraction(
        user_id=user.id,
        mail_call_log_id=call_log.id,
        provider_call_id=call_log.provider_call_id,
        interaction_order=(next_order[0] if next_order else 0) + 1,
        user_transcript=request.transcript or feedback_text,
        detected_intent="AGENT_FEEDBACK",
        email_reference=None,
        confidence=None,
        system_response_text=request.action_summary or feedback_text,
    )
    db.add(interaction)
    db.commit()
    return {"success": True, "message": "Feedback received.", "data": {"interaction_id": interaction.id}}


def dispatch_agent_tool(db: Session, request) -> dict[str, Any]:
    user = _get_user(db, request.user_id)
    if user is None:
        return {"success": False, "message": "I could not find that user.", "data": {}}

    action = (request.action or "").strip()
    if action == "get_today_summaries":
        data = get_today_summaries(db, user, request)
        return {"success": True, "message": data.get("message", "Action completed."), "data": data}
    if action == "get_email_detail":
        result = get_email_detail(db, user, request)
        if result.get("success") is False:
            return result
        return result
    if action == "search_email":
        return {"success": True, "message": "Action completed.", "data": search_email(db, user, request)}
    if action == "create_reminder":
        result = create_reminder_tool(db, user, request)
        if not result["success"]:
            return result
        return result
    if action == "create_recurring_reminder":
        result = create_recurring_reminder_tool(db, user, request)
        if not result["success"]:
            return result
        return result
    if action == "draft_email_reply":
        result = draft_email_reply_tool(db, user, request)
        if not result["success"]:
            return result
        return result
    if action == "send_email_reply":
        result = send_email_reply_tool(db, user, request)
        if not result["success"]:
            return result
        return result
    if action == "log_call_feedback":
        return log_call_feedback_tool(db, user, request)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported agent action")
