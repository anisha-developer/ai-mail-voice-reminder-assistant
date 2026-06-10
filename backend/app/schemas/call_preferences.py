from datetime import datetime

from pydantic import BaseModel, field_validator


VALID_MINIMUM_NEW_EMAILS_TO_CALL = {1, 3, 5}


class CallPreferenceSlot(BaseModel):
    time: str
    enabled: bool = True

    @field_validator("time")
    @classmethod
    def validate_time(cls, value: str) -> str:
        if not value or not isinstance(value, str):
            raise ValueError("Invalid time")
        try:
            hours, minutes = value.split(":")
            hour = int(hours)
            minute = int(minutes)
        except Exception as exc:
            raise ValueError("Time must be HH:MM") from exc
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("Time must be HH:MM")
        return f"{hour:02d}:{minute:02d}"


class CallPreferencesResponse(BaseModel):
    timezone: str
    call_slot_1_time: str
    call_slot_1_enabled: bool
    call_slot_2_time: str
    call_slot_2_enabled: bool
    call_slot_3_time: str
    call_slot_3_enabled: bool
    minimum_new_emails_to_call: int
    skip_if_no_new_emails: bool
    avoid_repeating_delivered_emails: bool
    next_scheduled_summary_call_at: datetime | None = None
    next_scheduled_summary_call_status: str | None = None
    pending_new_email_summaries: int = 0
    would_call_next_slot: bool = False
    next_slot_label: str | None = None
    next_slot_time: str | None = None


class UpdateCallPreferencesRequest(BaseModel):
    timezone: str | None = None
    call_slot_1_time: str | None = None
    call_slot_1_enabled: bool | None = None
    call_slot_2_time: str | None = None
    call_slot_2_enabled: bool | None = None
    call_slot_3_time: str | None = None
    call_slot_3_enabled: bool | None = None
    minimum_new_emails_to_call: int | None = None
    skip_if_no_new_emails: bool | None = None
    avoid_repeating_delivered_emails: bool | None = None

