from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.reminder import Reminder
from app.models.user import User

logger = logging.getLogger(__name__)


def _require_config() -> None:
    missing = []
    if not settings.elevenlabs_api_key:
        missing.append("ELEVENLABS_API_KEY")
    if not settings.elevenlabs_agent_id:
        missing.append("ELEVENLABS_AGENT_ID")
    if not settings.make_agent_webhook_url:
        missing.append("MAKE_AGENT_WEBHOOK_URL")
    if missing:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Missing ElevenLabs configuration: {', '.join(missing)}")


def build_elevenlabs_call_metadata(user: User, target: MailSummaryCallLog | Reminder) -> dict[str, Any]:
    return {
        "user_id": user.id,
        "user_email": user.email,
        "user_name": user.name,
        "timezone": user.timezone,
        "target_id": target.id,
        "target_type": target.__class__.__name__,
        "provider": "elevenlabs",
        "call_log_id": getattr(target, "id", None) if isinstance(target, MailSummaryCallLog) else None,
        "reminder_id": getattr(target, "id", None) if isinstance(target, Reminder) else None,
    }


def _safe_stub_response(kind: str, metadata: dict[str, Any]) -> dict[str, str]:
    logger.warning("ElevenLabs outbound %s is not yet enabled locally; returning safe stub response.", kind)
    return {
        "provider": "elevenlabs",
        "provider_call_id": f"elevenlabs-stub-{kind}-{metadata.get('target_id')}",
        "status": "queued",
    }


def start_mail_summary_call_with_elevenlabs(db: Session, user: User, call_log: MailSummaryCallLog) -> dict[str, str]:
    _require_config()
    metadata = build_elevenlabs_call_metadata(user, call_log)
    try:
        return _safe_stub_response("mail-summary", metadata)
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("ElevenLabs mail-summary call failed safely")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="ElevenLabs mail-summary call failed") from exc


def start_reminder_call_with_elevenlabs(db: Session, user: User, reminder: Reminder) -> dict[str, str]:
    _require_config()
    metadata = build_elevenlabs_call_metadata(user, reminder)
    try:
        return _safe_stub_response("reminder", metadata)
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("ElevenLabs reminder call failed safely")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="ElevenLabs reminder call failed") from exc
