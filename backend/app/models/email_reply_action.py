from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class EmailReplyAction(Base):
    __tablename__ = "email_reply_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    email_message_id: Mapped[int | None] = mapped_column(ForeignKey("email_messages.id"), nullable=True, index=True)
    mail_call_log_id: Mapped[int | None] = mapped_column(ForeignKey("mail_summary_call_logs.id"), nullable=True, index=True)
    voice_reply_session_id: Mapped[int | None] = mapped_column(ForeignKey("voice_reply_sessions.id"), nullable=True, index=True)
    gmail_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gmail_thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reply_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="drafted", nullable=False, index=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User")
    email_message = relationship("EmailMessage")
    mail_call_log = relationship("MailSummaryCallLog")
    voice_reply_session = relationship("VoiceReplySession")
