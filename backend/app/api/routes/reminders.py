from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.reminder import ReminderCreate, ReminderListResponse, ReminderResponse, ReminderSnoozeRequest, ReminderUpdate
from app.services.reminder_service import (
    call_again_reminder,
    cancel_reminder,
    create_reminder,
    get_reminder,
    list_reminders,
    mark_reminder_done,
    reminder_to_item,
    snooze_reminder,
    update_reminder,
)

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.post("", response_model=ReminderResponse)
def create(user_payload: ReminderCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReminderResponse:
    return ReminderResponse(**create_reminder(db, current_user, user_payload))


@router.get("", response_model=ReminderListResponse)
def list_all(include_cancelled: bool = Query(False), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReminderListResponse:
    reminders = list_reminders(db, current_user, include_cancelled=include_cancelled)
    return ReminderListResponse(value=[ReminderResponse(**reminder_to_item(reminder)) for reminder in reminders], count=len(reminders))


@router.get("/{reminder_id}", response_model=ReminderResponse)
def get_one(reminder_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReminderResponse:
    return ReminderResponse(**reminder_to_item(get_reminder(db, current_user, reminder_id)))


@router.patch("/{reminder_id}", response_model=ReminderResponse)
def patch_one(reminder_id: int, payload: ReminderUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReminderResponse:
    return ReminderResponse(**update_reminder(db, current_user, reminder_id, payload))


@router.delete("/{reminder_id}", response_model=ReminderResponse)
def delete_one(reminder_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReminderResponse:
    return ReminderResponse(**cancel_reminder(db, current_user, reminder_id))


@router.post("/{reminder_id}/call-again", response_model=ReminderResponse)
def call_again(reminder_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReminderResponse:
    return ReminderResponse(**reminder_to_item(call_again_reminder(db, current_user, reminder_id)))


@router.post("/{reminder_id}/snooze", response_model=ReminderResponse)
def snooze(reminder_id: int, payload: ReminderSnoozeRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReminderResponse:
    return ReminderResponse(**reminder_to_item(snooze_reminder(db, current_user, reminder_id, payload.minutes)))


@router.post("/{reminder_id}/mark-done", response_model=ReminderResponse)
def mark_done(reminder_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ReminderResponse:
    return ReminderResponse(**reminder_to_item(mark_reminder_done(db, current_user, reminder_id)))
