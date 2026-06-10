from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.recurring_reminder import RecurringReminderCreate, RecurringReminderListResponse, RecurringReminderResponse, RecurringReminderUpdate
from app.services.recurring_reminder_service import (
    cancel_recurring_rule,
    create_recurring_rule,
    get_recurring_rule_detail,
    get_rule_occurrences,
    get_user_recurring_rules,
    pause_recurring_rule,
    recurring_rule_to_item,
    resume_recurring_rule,
    update_recurring_rule,
)

router = APIRouter(prefix="/recurring-reminders", tags=["recurring-reminders"])


@router.get("", response_model=RecurringReminderListResponse)
def list_rules(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> RecurringReminderListResponse:
    rules = get_user_recurring_rules(db, current_user)
    return RecurringReminderListResponse(value=[RecurringReminderResponse(**recurring_rule_to_item(rule)) for rule in rules], count=len(rules))


@router.post("", response_model=RecurringReminderResponse)
def create_rule(payload: RecurringReminderCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> RecurringReminderResponse:
    return RecurringReminderResponse(**create_recurring_rule(db, current_user, payload))


@router.get("/{rule_id}", response_model=RecurringReminderResponse)
def get_rule(rule_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> RecurringReminderResponse:
    return RecurringReminderResponse(**recurring_rule_to_item(get_recurring_rule_detail(db, current_user, rule_id)))


@router.put("/{rule_id}", response_model=RecurringReminderResponse)
def put_rule(rule_id: int, payload: RecurringReminderUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> RecurringReminderResponse:
    return RecurringReminderResponse(**update_recurring_rule(db, current_user, rule_id, payload))


@router.post("/{rule_id}/pause", response_model=RecurringReminderResponse)
def pause_rule(rule_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> RecurringReminderResponse:
    return RecurringReminderResponse(**pause_recurring_rule(db, current_user, rule_id))


@router.post("/{rule_id}/resume", response_model=RecurringReminderResponse)
def resume_rule(rule_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> RecurringReminderResponse:
    return RecurringReminderResponse(**resume_recurring_rule(db, current_user, rule_id))


@router.post("/{rule_id}/cancel", response_model=RecurringReminderResponse)
def cancel_rule(rule_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> RecurringReminderResponse:
    return RecurringReminderResponse(**cancel_recurring_rule(db, current_user, rule_id))


@router.delete("/{rule_id}", response_model=RecurringReminderResponse)
def delete_rule(rule_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> RecurringReminderResponse:
    return RecurringReminderResponse(**cancel_recurring_rule(db, current_user, rule_id))


@router.get("/{rule_id}/occurrences")
def list_occurrences(rule_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    occurrences = get_rule_occurrences(db, current_user, rule_id)
    return {"value": [occurrence.id for occurrence in occurrences], "count": len(occurrences)}
