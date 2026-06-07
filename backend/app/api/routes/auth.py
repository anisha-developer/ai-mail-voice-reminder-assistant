from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.auth import AuthResponse, LoginRequest, SignupRequest
from app.services.auth_service import login, signup

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=AuthResponse)
def signup_route(payload: SignupRequest, db: Session = Depends(get_db)) -> AuthResponse:
    return signup(db, payload)


@router.post("/login", response_model=AuthResponse)
def login_route(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    return login(db, payload)

