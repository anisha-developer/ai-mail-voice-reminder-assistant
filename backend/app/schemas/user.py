from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserMeResponse(BaseModel):
    id: int
    name: str | None
    email: EmailStr
    phone_number: str | None = None
    timezone: str | None = None
    preferred_language: str | None = None
    created_at: datetime


class UpdateUserRequest(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    phone_number: str | None = Field(default=None, max_length=50)
    timezone: str | None = Field(default=None, max_length=100)
    preferred_language: str | None = Field(default=None, max_length=50)

