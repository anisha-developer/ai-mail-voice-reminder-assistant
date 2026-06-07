from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from urllib.parse import quote

from app.database.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.gmail import GmailConnectResponse, GmailStatusResponse
from app.services.gmail_oauth_service import can_send_replies, create_authorization_url, disconnect, get_status, store_tokens_from_callback

router = APIRouter(prefix="/gmail", tags=["gmail"])


@router.get("/connect", response_model=GmailConnectResponse)
def gmail_connect(current_user: User = Depends(get_current_user)) -> GmailConnectResponse:
    authorization_url, _state = create_authorization_url(current_user)
    return GmailConnectResponse(authorization_url=authorization_url)


@router.get("/callback")
def gmail_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        store_tokens_from_callback(db, state=state, code=code)
    except HTTPException as exc:
        return RedirectResponse(
            url=f"http://localhost:5173/settings?gmail=error&message={quote(str(exc.detail))}",
            status_code=302,
        )
    except Exception:
        return RedirectResponse(
            url="http://localhost:5173/settings?gmail=error&message=Gmail%20OAuth%20callback%20failed",
            status_code=302,
        )
    return RedirectResponse(url="http://localhost:5173/settings?gmail=connected", status_code=302)


@router.get("/status", response_model=GmailStatusResponse)
def gmail_status(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> GmailStatusResponse:
    connection = get_status(db, current_user.id)
    return GmailStatusResponse(
        is_connected=bool(connection and connection.is_connected),
        gmail_email=connection.gmail_email if connection else None,
        connected_at=connection.connected_at if connection else None,
        can_send_replies=can_send_replies(db, current_user.id),
    )


@router.delete("/disconnect")
def gmail_disconnect(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict[str, str]:
    disconnect(db, current_user.id)
    return {"message": "Gmail disconnected successfully"}
