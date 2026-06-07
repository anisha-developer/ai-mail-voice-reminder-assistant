from datetime import datetime

from pydantic import BaseModel, Field


class EmailSyncResponse(BaseModel):
    synced_count: int
    skipped_duplicates: int
    total_processed: int
    latest_gmail_received_at: datetime | None = None
    latest_stored_received_at: datetime | None = None
    gmail_returned_count: int | None = None
    inserted_email_ids: list[int] = Field(default_factory=list)
    inserted_gmail_message_ids: list[str] = Field(default_factory=list)


class EmailAttachmentMetadata(BaseModel):
    filename: str | None = None
    mime_type: str | None = None
    attachment_id: str | None = None
    size: int | None = None


class EmailListItem(BaseModel):
    id: int
    gmail_message_id: str
    gmail_thread_id: str | None = None
    sender: str | None = None
    recipient: str | None = None
    subject: str | None = None
    snippet: str | None = None
    received_at: datetime | None = None
    has_attachments: bool
    is_read_from_gmail: bool
    is_summarized: bool
    created_at: datetime
    updated_at: datetime


class EmailDetailResponse(EmailListItem):
    plain_body: str | None = None
    html_body: str | None = None
    attachment_metadata: list[EmailAttachmentMetadata] | None = None


class EmailSyncStatusResponse(BaseModel):
    last_sync_time: datetime | None = None
    total_emails_stored: int
    gmail_connected: bool


class EmailAutoSyncStatusResponse(BaseModel):
    auto_sync_enabled: bool
    interval_minutes: int
    last_auto_sync_at: datetime | None = None
    last_auto_sync_status: str | None = None
    last_auto_sync_error: str | None = None
    last_auto_sync_inserted_count: int = 0
    auto_summarize_after_sync: bool
    last_auto_summary_at: datetime | None = None
    last_auto_summary_status: str | None = None
    last_auto_summary_error: str | None = None
    last_auto_summary_success_count: int = 0
    last_auto_summary_failed_count: int = 0
    gmail_connected: bool
    unsummarized_email_count: int
