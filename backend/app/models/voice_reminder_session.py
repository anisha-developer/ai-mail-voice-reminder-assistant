from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class VoiceReminderSession(Base):
    __tablename__ = "voice_reminder_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    mail_call_log_id: Mapped[int] = mapped_column(ForeignKey("mail_summary_call_logs.id"), nullable=False, index=True)
    email_message_id: Mapped[int | None] = mapped_column(ForeignKey("email_messages.id"), nullable=True, index=True)
    email_summary_id: Mapped[int | None] = mapped_column(ForeignKey("email_summaries.id"), nullable=True, index=True)
    target_email_reference: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reminder_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reminder_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_timezone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reminder_phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="awaiting_details", nullable=False, index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    created_reminder_id: Mapped[int | None] = mapped_column(ForeignKey("reminders.id"), nullable=True, index=True)

    user = relationship("User")
    mail_call_log = relationship("MailSummaryCallLog")
    email_message = relationship("EmailMessage")
    email_summary = relationship("EmailSummary")
    created_reminder = relationship("Reminder")
