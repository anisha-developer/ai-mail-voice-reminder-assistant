from datetime import datetime

from pydantic import BaseModel


class ReplyStatusItem(BaseModel):
    id: int
    mail_call_id: int | str | None = None
    call_id: str | None = None
    email_number: int | None = None
    original_email_id: int | None = None
    original_summary_id: int | None = None
    original_sender: str | None = None
    original_subject: str | None = None
    reply_text: str | None = None
    status: str
    failure_reason: str | None = None
    source: str
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None = None


class ReplyStatusListResponse(BaseModel):
    value: list[ReplyStatusItem]
    count: int
