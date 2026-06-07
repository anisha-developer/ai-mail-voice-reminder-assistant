from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.email_reply import EmailReplyActionItem, EmailReplyListResponse
from app.services.gmail_reply_service import get_reply_action, list_reply_actions

router = APIRouter(prefix="/email-replies", tags=["email-replies"])


@router.get("", response_model=EmailReplyListResponse)
def list_email_replies(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> EmailReplyListResponse:
    actions = list_reply_actions(db, current_user)
    return EmailReplyListResponse(value=[EmailReplyActionItem(**action.__dict__) for action in actions], count=len(actions))


@router.get("/{reply_id}", response_model=EmailReplyActionItem)
def get_email_reply(reply_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> EmailReplyActionItem:
    action = get_reply_action(db, current_user, reply_id)
    return EmailReplyActionItem(**action.__dict__)
