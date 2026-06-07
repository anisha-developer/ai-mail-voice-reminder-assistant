from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.user import UpdateUserRequest, UserMeResponse
from app.services.user_service import get_me, update_me

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserMeResponse)
def read_me(current_user: User = Depends(get_current_user)) -> UserMeResponse:
    return get_me(current_user)


@router.put("/me", response_model=UserMeResponse)
def update_me_route(
    payload: UpdateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserMeResponse:
    return update_me(db, current_user, payload)

