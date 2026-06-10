from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class AgentToolRequest(BaseModel):
    action: str
    user_id: int
    call_id: str | None = None
    email_reference: int | None = None
    email_summary_id: int | None = None
    email_message_id: int | None = None
    query: str | None = None
    title: str | None = None
    notes: str | None = None
    reminder_time_text: str | None = None
    reminder_at: str | None = None
    repeat_type: str | None = None
    interval_value: int | None = None
    interval_unit: str | None = None
    time_of_day: str | None = None
    days_of_week: list[str] | None = None
    day_of_month: int | None = None
    reply_instruction: str | None = None
    draft_id: int | None = None
    timezone: str | None = None
    transcript: str | None = None
    action_summary: str | None = None
    feedback_text: str | None = None

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

        def _to_days_of_week(value: Any) -> Any:
            value = _empty_to_none(value)
            if value is None:
                return None
            if isinstance(value, list):
                cleaned = [str(item).strip() for item in value if str(item).strip()]
                return cleaned or None
            if isinstance(value, str):
                cleaned = [item.strip() for item in value.split(",") if item.strip()]
                return cleaned or None
            return value

        for key in (
            "email_reference",
            "email_summary_id",
            "email_message_id",
            "interval_value",
            "day_of_month",
            "draft_id",
            "user_id",
        ):
            if key in values:
                values[key] = _to_int(values[key])

        for key in (
            "query",
            "title",
            "notes",
            "reminder_time_text",
            "reminder_at",
            "repeat_type",
            "interval_unit",
            "time_of_day",
            "reply_instruction",
            "timezone",
            "transcript",
            "action_summary",
            "feedback_text",
        ):
            if key in values:
                values[key] = _empty_to_none(values[key])

        if "days_of_week" in values:
            values["days_of_week"] = _to_days_of_week(values["days_of_week"])

        return values


class AgentToolResponse(BaseModel):
    success: bool
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class AgentElevenLabsPostCallRequest(BaseModel):
    call_id: int | str | None = None
    user_id: int | None = None
    provider_call_id: str | None = None
    transcript: str | None = None
    summary_text: str | None = None
    action_summary: str | None = None
    action: str | None = None
    confidence: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_payload(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values

        for key in ("call_id", "user_id"):
            value = values.get(key)
            if isinstance(value, str) and value.strip().lstrip("-").isdigit():
                values[key] = int(value.strip())
            elif isinstance(value, str) and not value.strip():
                values[key] = None

        for key in ("provider_call_id", "transcript", "summary_text", "action_summary", "action", "confidence"):
            value = values.get(key)
            if isinstance(value, str) and not value.strip():
                values[key] = None
        return values
