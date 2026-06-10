from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field, field_validator


class ReminderCreate(BaseModel):
    type: str | None = None
    title: str
    notes: str | None = None
    reminder_date: str
    reminder_time: str | None = None
    time_of_day: str | None = None
    timezone: str | None = None
    phone_number: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Title is required")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            return None
        try:
            ZoneInfo(value)
        except Exception as exc:
            raise ValueError("Invalid timezone") from exc
        return value

    @field_validator("reminder_time", "time_of_day")
    @classmethod
    def validate_time_of_day(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            return None
        parts = value.split(":")
        if len(parts) != 2 or any(not part.isdigit() for part in parts):
            raise ValueError("Time must be HH:MM")
        hour, minute = map(int, parts)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("Time must be HH:MM")
        return f"{hour:02d}:{minute:02d}"


class ReminderUpdate(BaseModel):
    title: str | None = None
    notes: str | None = None
    reminder_date: str | None = None
    reminder_time: str | None = None
    time_of_day: str | None = None
    timezone: str | None = None
    phone_number: str | None = None
    status: str | None = None


class ReminderSnoozeRequest(BaseModel):
    minutes: int = Field(default=10, ge=1, le=1440)


class ReminderResponse(BaseModel):
    id: int
    title: str
    notes: str | None = None
    reminder_at: datetime
    timezone: str | None = None
    phone_number: str | None = None
    status: str
    retry_count: int = 0
    max_retry_attempts: int = 3
    next_retry_at: datetime | None = None
    last_call_status: str | None = None
    provider: str | None = None
    provider_call_id: str | None = None
    called_at: datetime | None = None
    last_error: str | None = None
    completed_manually_at: datetime | None = None
    snoozed_until: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ReminderListResponse(BaseModel):
    value: list[ReminderResponse] = Field(default_factory=list)
    count: int = 0
