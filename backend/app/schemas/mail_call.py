from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel, Field, model_validator

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


class VoiceMailCallReplyRequest(BaseModel):
    email_number: int | str | None = None
    reply_text: str | None = None
    confirmed: bool | str | None = False
    call_id: int | str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_payload(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values

        def _empty_to_none(value: Any) -> Any:
            if value is None:
                return None
            if isinstance(value, str) and not value.strip():
                return None
            return value

        def _to_int(value: Any) -> Any:
            value = _empty_to_none(value)
            if value is None:
                return None
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.strip().lstrip("-").isdigit():
                return int(value.strip())
            return value

        for key in ("email_number", "call_id"):
            if key in values:
                values[key] = _to_int(values[key])

        if "reply_text" in values:
            values["reply_text"] = _empty_to_none(values["reply_text"])

        confirmed = values.get("confirmed")
        if isinstance(confirmed, str):
            normalized = confirmed.strip().lower()
            if normalized in {"true", "1", "yes", "y", "on"}:
                values["confirmed"] = True
            elif normalized in {"false", "0", "no", "n", "off"}:
                values["confirmed"] = False
            elif not normalized:
                values["confirmed"] = None

        return values


class VoiceMailCallReplyResponse(BaseModel):
    success: bool
    status: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class VoiceMailCallReminderRequest(BaseModel):
    mail_call_id: int | str | None = None
    email_number: int | str | None = None
    reminder_text: str | None = None
    remind_at: datetime | str | None = None
    reminder_time_text: str | None = None
    confirmed: bool | str | None = False
    call_id: int | str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_payload(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values

        def _empty_to_none(value: Any) -> Any:
            if value is None:
                return None
            if isinstance(value, str) and not value.strip():
                return None
            return value

        def _to_int(value: Any) -> Any:
            value = _empty_to_none(value)
            if value is None:
                return None
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.strip().lstrip("-").isdigit():
                return int(value.strip())
            return value

        for key in ("mail_call_id", "email_number", "call_id"):
            if key in values:
                values[key] = _to_int(values[key])

        for key in ("reminder_text", "reminder_time_text"):
            if key in values:
                values[key] = _empty_to_none(values[key])

        remind_at = values.get("remind_at")
        if isinstance(remind_at, str):
            values["remind_at"] = remind_at.strip() or None

        confirmed = values.get("confirmed")
        if isinstance(confirmed, str):
            normalized = confirmed.strip().lower()
            if normalized in {"true", "1", "yes", "y", "on"}:
                values["confirmed"] = True
            elif normalized in {"false", "0", "no", "n", "off"}:
                values["confirmed"] = False
            elif not normalized:
                values["confirmed"] = None

        return values


class VoiceMailCallReminderResponse(BaseModel):
    success: bool
    status: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
