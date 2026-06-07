from datetime import datetime

from pydantic import BaseModel


class EmailReplyActionItem(BaseModel):
    id: int
    user_id: int
    email_message_id: int | None = None
    mail_call_log_id: int | None = None
    voice_reply_session_id: int | None = None
    gmail_message_id: str | None = None
    gmail_thread_id: str | None = None
    reply_body: str | None = None
    status: str
    provider_message_id: str | None = None
    error_message: str | None = None
    created_at: datetime
    sent_at: datetime | None = None


class EmailReplyListResponse(BaseModel):
    value: list[EmailReplyActionItem]
    count: int
