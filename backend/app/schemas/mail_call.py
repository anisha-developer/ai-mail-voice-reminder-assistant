from datetime import date, datetime, time

from pydantic import BaseModel

from app.schemas.summary import SummaryListItem


class MailCallCountResponse(BaseModel):
    max_calls_per_day: int
    used_calls_today: int
    remaining_calls_today: int
    date: date
    total_summaries_in_database: int
    today_summaries_count: int
    pending_today_summaries_count: int


class MailCallPrepareResponse(BaseModel):
    call_log_id: int
    summary_count: int
    script_text: str
    today_summaries_count: int
    pending_today_summaries_count: int
    used_calls_today: int
    remaining_calls_today: int


class MailCallHistoryItem(BaseModel):
    id: int
    call_type: str
    call_status: str
    call_date: date
    call_time: time
    summary_count: int
    script_text: str | None = None
    provider: str | None = None
    provider_call_id: str | None = None
    to_phone_number: str | None = None
    from_phone_number: str | None = None
    call_started_at: datetime | None = None
    call_completed_at: datetime | None = None
    call_duration_seconds: int | None = None
    provider_status: str | None = None
    provider_error_message: str | None = None
    delivery_status: str
    delivered_summary_ids: list[int]
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class MailCallMarkDeliveredResponse(BaseModel):
    success: bool
    call_log_id: int
    delivered_summary_count: int
    message: str


class PendingSummariesResponse(BaseModel):
    pending_count: int
    pending_today_count: int
    today_summaries_count: int
    total_summaries_in_database: int
    summaries: list[SummaryListItem]


class VoiceCallStartResponse(BaseModel):
    call_log_id: int
    provider: str
    provider_call_id: str
    call_status: str


class VoiceCallInteractionItem(BaseModel):
    id: int
    user_transcript: str | None = None
    detected_intent: str
    email_reference: int | None = None
    confidence: str | None = None
    system_response_text: str | None = None
    interaction_order: int
    created_at: datetime
