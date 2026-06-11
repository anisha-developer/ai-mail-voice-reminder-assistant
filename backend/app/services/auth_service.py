from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.core.timezone import DEFAULT_TIMEZONE, normalize_timezone_name
from app.models.user import User
from app.models.user_call_preference import UserCallPreference
from app.models.user_preference import UserPreference
from app.schemas.auth import AuthResponse, AuthUserResponse, LoginRequest, SignupRequest


def _to_auth_user(user: User) -> AuthUserResponse:
    return AuthUserResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        phone_number=user.phone_number,
        timezone=user.timezone,
        preferred_language=user.preferred_language,
    )


def signup(db: Session, payload: SignupRequest) -> AuthResponse:
    existing_user = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    timezone_name = normalize_timezone_name(payload.timezone, DEFAULT_TIMEZONE)
    user = User(
        email=payload.email.lower(),
        name=payload.name,
        phone_number=payload.phone_number,
        timezone=timezone_name,
        preferred_language=payload.preferred_language,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.flush()

    preferences = UserPreference(
        user_id=user.id,
        timezone=timezone_name,
        preferred_language=payload.preferred_language,
        max_mail_summary_calls_per_day=3,
    )
    db.add(preferences)
    call_preferences = UserCallPreference(
        user_id=user.id,
        timezone=timezone_name,
    )
    db.add(call_preferences)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.email)
    return AuthResponse(access_token=token, user=_to_auth_user(user))


def login(db: Session, payload: LoginRequest) -> AuthResponse:
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not user.hashed_password or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token(user.email)
    return AuthResponse(access_token=token, user=_to_auth_user(user))
