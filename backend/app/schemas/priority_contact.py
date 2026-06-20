from datetime import datetime

from pydantic import BaseModel, field_validator


class PriorityContactCreate(BaseModel):
    display_name: str
    email_address: str
    relationship: str | None = "Other"
    priority_level: int | None = 1
    notes: str | None = None

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Display name is required")
        return value.strip()

    @field_validator("email_address")
    @classmethod
    def validate_email_address(cls, value: str) -> str:
        email = (value or "").strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValueError("Invalid email address")
        return email

    @field_validator("relationship")
    @classmethod
    def validate_relationship(cls, value: str | None) -> str:
        return (value or "Other").strip() or "Other"


class PriorityContactUpdate(BaseModel):
    display_name: str | None = None
    email_address: str | None = None
    relationship: str | None = None
    priority_level: int | None = None
    notes: str | None = None

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("Display name is required")
        return value.strip()

    @field_validator("email_address")
    @classmethod
    def validate_email_address(cls, value: str | None) -> str | None:
        if value is None:
            return value
        email = value.strip().lower()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValueError("Invalid email address")
        return email

    @field_validator("relationship")
    @classmethod
    def validate_relationship(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return value.strip() or "Other"


class PriorityContactResponse(BaseModel):
    id: int
    user_id: int
    display_name: str
    email_address: str
    relationship: str | None = None
    priority_level: int
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
