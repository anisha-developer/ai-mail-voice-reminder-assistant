from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class VoiceEmailReplyLog(Base):
    __tablename__ = "voice_email_reply_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    mail_call_id: Mapped[int | str | None] = mapped_column(String(50), nullable=True, index=True)
    call_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    email_number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    original_email_id: Mapped[int | None] = mapped_column(ForeignKey("email_messages.id"), nullable=True, index=True)
    original_summary_id: Mapped[int | None] = mapped_column(ForeignKey("email_summaries.id"), nullable=True, index=True)
    original_sender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reply_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False, index=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="voice_call", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="voice_email_reply_logs")
    original_email = relationship("EmailMessage")
    original_summary = relationship("EmailSummary")
