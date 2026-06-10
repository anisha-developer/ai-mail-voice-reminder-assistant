from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.call_preferences import CallPreferencesResponse, UpdateCallPreferencesRequest
from app.services.call_preferences_service import call_preferences_to_item, get_or_create_call_preferences, update_call_preferences

router = APIRouter(prefix="/call-preferences", tags=["call-preferences"])


@router.get("", response_model=CallPreferencesResponse)
def get_preferences(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> CallPreferencesResponse:
    prefs = get_or_create_call_preferences(db, current_user)
    return CallPreferencesResponse(**call_preferences_to_item(db, current_user, prefs))


@router.put("", response_model=CallPreferencesResponse)
def put_preferences(
    payload: UpdateCallPreferencesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CallPreferencesResponse:
    prefs = update_call_preferences(db, current_user, payload)
    return CallPreferencesResponse(**call_preferences_to_item(db, current_user, prefs))
