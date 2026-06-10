from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

RepeatType = Literal["none", "daily", "weekly", "monthly", "weekdays", "custom_days", "custom_interval"]
IntervalUnit = Literal["minutes", "hours", "days", "weeks", "months"]
RuleStatus = Literal["active", "paused", "cancelled", "ended"]


class RecurringReminderBase(BaseModel):
    type: str | None = None
    title: str
    notes: str | None = None
    timezone: str
    repeat_type: RepeatType
    interval_value: int | None = None
    interval_unit: IntervalUnit | None = None
    days_of_week: list[str] | None = None
    day_of_month: int | None = None
    time_of_day: str | None = None
    source_type: str | None = None
    email_message_id: int | None = None
    email_summary_id: int | None = None

    @field_validator("title")
    @classmethod
    def title_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title is required")
        return value

    @field_validator("timezone")
    @classmethod
    def timezone_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Timezone is required")
        return value

    @field_validator("time_of_day")
    @classmethod
    def validate_time_of_day(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            return None
        parts = value.split(":")
        if len(parts) != 2 or any(not part.isdigit() for part in parts):
            raise ValueError("time_of_day must be HH:MM")
        hour, minute = map(int, parts)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("time_of_day must be HH:MM")
        return f"{hour:02d}:{minute:02d}"

    @field_validator("days_of_week")
    @classmethod
    def validate_days_of_week(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        normalized = [item.strip().lower() for item in value if item and item.strip()]
        if not normalized:
            return None
        allowed = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
        if any(day not in allowed for day in normalized):
            raise ValueError("Invalid day of week")
        return normalized

    @field_validator("day_of_month")
    @classmethod
    def validate_day_of_month(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if value < 1 or value > 31:
            raise ValueError("day_of_month must be between 1 and 31")
        return value

    @field_validator("interval_value")
    @classmethod
    def validate_interval_value(cls, value: int | None) -> int | None:
        if value is None:
            return value
        if value <= 0:
            raise ValueError("interval_value must be positive")
        return value

class RecurringReminderCreate(RecurringReminderBase):
    pass


class RecurringReminderUpdate(BaseModel):
    title: str | None = None
    notes: str | None = None
    timezone: str | None = None
    repeat_type: RepeatType | None = None
    interval_value: int | None = None
    interval_unit: IntervalUnit | None = None
    days_of_week: list[str] | None = None
    day_of_month: int | None = None
    time_of_day: str | None = None
    is_active: bool | None = None
    source_type: str | None = None
    email_message_id: int | None = None
    email_summary_id: int | None = None


class RecurringReminderResponse(BaseModel):
    id: int
    user_id: int
    title: str
    notes: str | None = None
    timezone: str
    repeat_type: str
    interval_value: int | None = None
    interval_unit: str | None = None
    days_of_week: list[str] | None = None
    day_of_month: int | None = None
    time_of_day: str | None = None
    is_active: bool
    paused_at: datetime | None = None
    cancelled_at: datetime | None = None
    last_generated_at: datetime | None = None
    next_occurrence_at: datetime | None = None
    source_type: str | None = None
    email_message_id: int | None = None
    email_summary_id: int | None = None
    created_at: datetime
    updated_at: datetime
    status: RuleStatus


class RecurringReminderListResponse(BaseModel):
    value: list[RecurringReminderResponse] = Field(default_factory=list)
    count: int = 0
