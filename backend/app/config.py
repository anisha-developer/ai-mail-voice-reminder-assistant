from functools import lru_cache
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Mail Summary and Voice Reminder Assistant"
    environment: str = "development"
    debug: bool = True
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/ai_mail_assistant"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60 * 24
    jwt_algorithm: str = "HS256"
    cors_origins: str = "http://localhost:5173"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/gmail/callback"
    google_scopes: str = "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send"
    token_encryption_key: str = ""
    oauth_state_secret: str = ""
    redis_url: str = "redis://redis:6379/0"
    llm_provider: str = "mock"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    voice_provider: str = "twilio"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_phone: str = ""
    twilio_verified_caller_id: str = ""
    public_backend_url: str = "http://localhost:8000"
    auto_email_sync_enabled: bool = False
    auto_email_sync_interval_minutes: int = 5
    auto_email_sync_batch_users: int = 20
    auto_email_sync_max_results: int = 50
    auto_email_sync_max_pages: int = 2
    auto_summarize_after_sync: bool = False
    reminder_calls_enabled: bool = False
    reminder_check_interval_seconds: int = 60
    reminder_due_grace_seconds: int = 120

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def scheduler_run_identifier(self) -> str:
        return os.environ.get("RUN_MAIN", "")

@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
