from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.mail_call import (
    MailCallCountResponse,
    MailCallHistoryItem,
    MailCallMarkDeliveredResponse,
    MailCallPrepareResponse,
    PendingSummariesResponse,
)
from app.schemas.summary import SummaryListItem
from app.services.mail_summary_call_service import (
    get_mail_call_count_today,
    list_mail_call_history,
    mail_call_to_item,
    mark_mail_call_delivered,
    pending_summaries_payload,
    prepare_mail_summary_call,
)

router = APIRouter(prefix="/mail-calls", tags=["mail-calls"])


@router.get("/count-today", response_model=MailCallCountResponse)
def get_count_today(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MailCallCountResponse:
    return MailCallCountResponse(**get_mail_call_count_today(db, current_user))


@router.post("/prepare", response_model=MailCallPrepareResponse)
def prepare_call(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MailCallPrepareResponse:
    return MailCallPrepareResponse(**prepare_mail_summary_call(db, current_user))


@router.post("/{call_log_id}/mark-delivered", response_model=MailCallMarkDeliveredResponse)
def mark_delivered(call_log_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MailCallMarkDeliveredResponse:
    return MailCallMarkDeliveredResponse(**mark_mail_call_delivered(db, current_user, call_log_id))


@router.get("/history", response_model=list[MailCallHistoryItem])
def get_history(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[MailCallHistoryItem]:
    history = list_mail_call_history(db, current_user)
    return [MailCallHistoryItem(**mail_call_to_item(item)) for item in history]


@router.get("/pending-summaries", response_model=PendingSummariesResponse)
def get_pending_summaries(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> PendingSummariesResponse:
    payload = pending_summaries_payload(db, current_user)
    payload["summaries"] = [SummaryListItem(**item) for item in payload["summaries"]]
    return PendingSummariesResponse(**payload)
