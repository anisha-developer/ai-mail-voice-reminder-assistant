from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.reply_status import ReplyStatusItem, ReplyStatusListResponse
from app.services.reply_status_service import build_reply_status_item, get_reply_status_log, list_reply_status_logs

router = APIRouter(prefix="/reply-status", tags=["reply-status"])


@router.get("", response_model=ReplyStatusListResponse)
def list_reply_status(
    status: str | None = None,
    source: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReplyStatusListResponse:
    logs = list_reply_status_logs(db, current_user, status_filter=status, source_filter=source)
    return ReplyStatusListResponse(value=[ReplyStatusItem(**build_reply_status_item(log)) for log in logs], count=len(logs))


@router.get("/{log_id}", response_model=ReplyStatusItem)
def get_reply_status(
    log_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReplyStatusItem:
    log = get_reply_status_log(db, current_user, log_id)
    return ReplyStatusItem(**build_reply_status_item(log))
