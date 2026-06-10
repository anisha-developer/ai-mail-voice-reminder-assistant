from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database.session import get_db
from app.schemas.agent_tools import AgentElevenLabsPostCallRequest, AgentToolRequest, AgentToolResponse
from app.services.agent_tool_service import dispatch_agent_tool
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.voice_call_interaction import VoiceCallInteraction
from datetime import datetime, timezone

router = APIRouter(prefix="/agent", tags=["agent-tools"])


def _verify_agent_key(x_agent_api_key: str | None) -> None:
    configured_key = (settings.agent_tool_api_key or "").strip()
    if not configured_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AGENT_TOOL_API_KEY is not configured")
    if not x_agent_api_key or not secrets.compare_digest(x_agent_api_key, configured_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


@router.post("/tools", response_model=AgentToolResponse)
def agent_tools_route(
    payload: AgentToolRequest,
    db: Session = Depends(get_db),
    x_agent_api_key: str | None = Header(default=None, alias="X-Agent-API-Key"),
) -> AgentToolResponse:
    _verify_agent_key(x_agent_api_key)
    result = dispatch_agent_tool(db, payload)
    if "success" not in result:
        result = {"success": True, "message": "Action completed.", "data": result}
    return AgentToolResponse(**result)


@router.post("/elevenlabs/post-call", response_model=AgentToolResponse)
def elevenlabs_post_call_route(
    payload: AgentElevenLabsPostCallRequest,
    db: Session = Depends(get_db),
    x_agent_api_key: str | None = Header(default=None, alias="X-Agent-API-Key"),
) -> AgentToolResponse:
    _verify_agent_key(x_agent_api_key)

    call_log = None
    if isinstance(payload.call_id, int):
        call_log = db.query(MailSummaryCallLog).filter(MailSummaryCallLog.id == payload.call_id).first()

    if call_log is None:
        return AgentToolResponse(
            success=True,
            message="Post-call payload received.",
            data={"stored": False},
        )

    next_order = (
        db.query(VoiceCallInteraction.interaction_order)
        .filter(VoiceCallInteraction.mail_call_log_id == call_log.id)
        .order_by(VoiceCallInteraction.interaction_order.desc())
        .first()
    )
    interaction = VoiceCallInteraction(
        user_id=call_log.user_id,
        mail_call_log_id=call_log.id,
        provider_call_id=payload.provider_call_id or call_log.provider_call_id,
        interaction_order=(next_order[0] if next_order else 0) + 1,
        user_transcript=payload.transcript or payload.summary_text,
        detected_intent="AGENT_POST_CALL",
        email_reference=None,
        confidence=payload.confidence,
        system_response_text=payload.action_summary or payload.action or payload.summary_text,
    )
    db.add(interaction)
    db.commit()

    call_log.updated_at = datetime.now(timezone.utc)
    db.add(call_log)
    db.commit()

    return AgentToolResponse(
        success=True,
        message="Post-call payload received.",
        data={"stored": True, "interaction_id": interaction.id},
    )
