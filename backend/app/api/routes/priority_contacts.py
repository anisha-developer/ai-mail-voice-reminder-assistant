from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.priority_contact import PriorityContactCreate, PriorityContactResponse, PriorityContactUpdate
from app.services.priority_contact_service import (
    create_priority_contact,
    delete_priority_contact,
    get_priority_contact,
    list_priority_contacts,
    priority_contact_to_item,
    update_priority_contact,
)

router = APIRouter(prefix="/priority-contacts", tags=["priority-contacts"])


@router.get("", response_model=list[PriorityContactResponse])
def get_priority_contacts(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[PriorityContactResponse]:
    return [PriorityContactResponse(**priority_contact_to_item(contact)) for contact in list_priority_contacts(db, current_user)]


@router.post("", response_model=PriorityContactResponse)
def create_priority_contact_route(
    payload: PriorityContactCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PriorityContactResponse:
    return PriorityContactResponse(**priority_contact_to_item(create_priority_contact(db, current_user, payload)))


@router.put("/{contact_id}", response_model=PriorityContactResponse)
def update_priority_contact_route(
    contact_id: int,
    payload: PriorityContactUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PriorityContactResponse:
    return PriorityContactResponse(**priority_contact_to_item(update_priority_contact(db, current_user, contact_id, payload)))


@router.delete("/{contact_id}", response_model=PriorityContactResponse)
def delete_priority_contact_route(
    contact_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PriorityContactResponse:
    return PriorityContactResponse(**priority_contact_to_item(delete_priority_contact(db, current_user, contact_id)))
