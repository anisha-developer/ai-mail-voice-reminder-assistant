from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone_number: str | None = Field(default=None, max_length=50)
    timezone: str | None = Field(default=None, max_length=100)
    preferred_language: str | None = Field(default=None, max_length=50)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AuthUserResponse(BaseModel):
    id: int
    name: str | None
    email: EmailStr
    phone_number: str | None = None
    timezone: str | None = None
    preferred_language: str | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserResponse

