from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class EmailSummary(Base):
    __tablename__ = "email_summaries"
    __table_args__ = (UniqueConstraint("email_message_id", name="uq_email_summaries_email_message_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    email_message_id: Mapped[int] = mapped_column(ForeignKey("email_messages.id"), nullable=False, index=True)
    sender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    short_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    detailed_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_required_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_delivered_in_mail_call: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mail_call_log_id: Mapped[int | None] = mapped_column(ForeignKey("mail_summary_call_logs.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)

    user = relationship("User", back_populates="email_summaries")
    email_message = relationship("EmailMessage")
    mail_call_log = relationship("MailSummaryCallLog", back_populates="delivered_summaries")
