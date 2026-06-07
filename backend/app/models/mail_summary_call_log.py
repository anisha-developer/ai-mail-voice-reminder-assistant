from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, Time, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class MailSummaryCallLog(Base):
    __tablename__ = "mail_summary_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    call_type: Mapped[str] = mapped_column(String(50), default="mail_summary", nullable=False, index=True)
    call_status: Mapped[str] = mapped_column(String(50), default="prepared", nullable=False, index=True)
    call_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    call_time: Mapped[time] = mapped_column(Time, nullable=False)
    summary_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    script_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False, index=True)
    delivered_summary_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    to_phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    from_phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    call_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    call_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    call_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)

    user = relationship("User", back_populates="mail_summary_call_logs")
    delivered_summaries = relationship("EmailSummary", back_populates="mail_call_log")
    voice_call_interactions = relationship("VoiceCallInteraction", back_populates="mail_call_log", cascade="all, delete-orphan")
