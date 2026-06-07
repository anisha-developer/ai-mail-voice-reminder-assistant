from datetime import datetime

from pydantic import BaseModel


class SummaryGenerateResponse(BaseModel):
    processed_count: int
    success_count: int
    failed_count: int
    already_summarized_count: int


class SummaryListItem(BaseModel):
    id: int
    email_message_id: int
    sender: str | None = None
    subject: str | None = None
    short_summary: str | None = None
    action_required_text: str | None = None
    attachment_note: str | None = None
    summary_status: str
    error_message: str | None = None
    is_delivered_in_mail_call: bool = False
    delivered_at: datetime | None = None
    mail_call_log_id: int | None = None
    created_at: datetime
    updated_at: datetime


class SummaryDetailResponse(SummaryListItem):
    detailed_summary: str | None = None


class SummaryDetailTextResponse(BaseModel):
    summary_id: int
    detailed_summary: str | None = None
