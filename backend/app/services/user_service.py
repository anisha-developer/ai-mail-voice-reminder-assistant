from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_call_preference import UserCallPreference
from app.models.user_preference import UserPreference
from app.core.timezone import normalize_timezone_name
from app.schemas.user import UpdateUserRequest, UserMeResponse


def get_me(user: User) -> UserMeResponse:
    return UserMeResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        phone_number=user.phone_number,
        timezone=user.timezone,
        preferred_language=user.preferred_language,
        created_at=user.created_at,
    )


def update_me(db: Session, user: User, payload: UpdateUserRequest) -> UserMeResponse:
    for field in ["name", "phone_number", "timezone", "preferred_language"]:
        value = getattr(payload, field)
        if value is not None:
            if field == "timezone":
                setattr(user, field, normalize_timezone_name(value, user.timezone or "Asia/Kolkata"))
            else:
                setattr(user, field, value)

    db.add(user)
    preferences = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    if preferences:
        if payload.timezone is not None:
            preferences.timezone = normalize_timezone_name(payload.timezone, preferences.timezone or user.timezone or "Asia/Kolkata")
        if payload.preferred_language is not None:
            preferences.preferred_language = payload.preferred_language
        db.add(preferences)
    call_preferences = db.query(UserCallPreference).filter(UserCallPreference.user_id == user.id).first()
    if call_preferences and payload.timezone is not None:
        call_preferences.timezone = normalize_timezone_name(payload.timezone, call_preferences.timezone or user.timezone or "Asia/Kolkata")
        db.add(call_preferences)
    db.commit()
    db.refresh(user)
    return get_me(user)
