from datetime import datetime

from pydantic import BaseModel, HttpUrl


class GmailConnectResponse(BaseModel):
    authorization_url: HttpUrl


class GmailStatusResponse(BaseModel):
    is_connected: bool
    gmail_email: str | None = None
    connected_at: datetime | None = None
    can_send_replies: bool = False


class GmailCallbackResponse(BaseModel):
    success: bool
    message: str
