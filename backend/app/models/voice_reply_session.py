from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class VoiceReplySession(Base):
    __tablename__ = "voice_reply_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    mail_call_log_id: Mapped[int] = mapped_column(ForeignKey("mail_summary_call_logs.id"), nullable=False, index=True)
    email_message_id: Mapped[int | None] = mapped_column(ForeignKey("email_messages.id"), nullable=True, index=True)
    email_summary_id: Mapped[int | None] = mapped_column(ForeignKey("email_summaries.id"), nullable=True, index=True)
    target_email_reference: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reply_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="awaiting_body", nullable=False, index=True)
    gmail_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gmail_thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    to_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User")
    mail_call_log = relationship("MailSummaryCallLog")
    email_message = relationship("EmailMessage")
    email_summary = relationship("EmailSummary")
