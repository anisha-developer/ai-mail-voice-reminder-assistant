from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.email import (
    EmailAutoSyncStatusResponse,
    EmailDetailResponse,
    EmailListItem,
    EmailSyncResponse,
    EmailSyncStatusResponse,
)
from app.services.auto_email_sync_service import get_auto_sync_status
from app.services.gmail_email_service import (
    email_to_detail,
    email_to_list_item,
    get_sync_status,
    get_user_email,
    list_user_emails,
    sync_user_emails,
)

router = APIRouter(prefix="/emails", tags=["emails"])


@router.post("/sync", response_model=EmailSyncResponse)
def sync_emails(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    max_results: int = Query(50, ge=1, le=500),
    max_pages: int = Query(3, ge=1, le=20),
) -> EmailSyncResponse:
    result = sync_user_emails(db, current_user, max_results=max_results, max_pages=max_pages)
    return EmailSyncResponse(**result)


@router.get("", response_model=list[EmailListItem])
def list_emails(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> list[EmailListItem]:
    items, _total = list_user_emails(db, current_user.id, page, limit)
    return [EmailListItem(**email_to_list_item(item)) for item in items]


@router.get("/sync-status", response_model=EmailSyncStatusResponse)
def email_sync_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> EmailSyncStatusResponse:
    return EmailSyncStatusResponse(**get_sync_status(db, current_user.id))


@router.get("/auto-sync-status", response_model=EmailAutoSyncStatusResponse)
def email_auto_sync_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> EmailAutoSyncStatusResponse:
    return EmailAutoSyncStatusResponse(**get_auto_sync_status(db, current_user))


@router.get("/{email_id}", response_model=EmailDetailResponse)
def get_email(
    email_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> EmailDetailResponse:
    email = get_user_email(db, current_user.id, email_id)
    return EmailDetailResponse(**email_to_detail(email))
