from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_preference import UserPreference
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
            setattr(user, field, value)

    db.add(user)
    preferences = db.query(UserPreference).filter(UserPreference.user_id == user.id).first()
    if preferences:
        if payload.timezone is not None:
            preferences.timezone = payload.timezone
        if payload.preferred_language is not None:
            preferences.preferred_language = payload.preferred_language
        db.add(preferences)
    db.commit()
    db.refresh(user)
    return get_me(user)
