from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class RecurringReminderRule(Base):
    __tablename__ = "recurring_reminder_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="UTC")
    repeat_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    interval_value: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interval_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    days_of_week: Mapped[str | None] = mapped_column(Text, nullable=True)
    day_of_month: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_of_day: Mapped[str | None] = mapped_column(String(5), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_occurrence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    email_summary_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)

    user = relationship("User", back_populates="recurring_reminder_rules")
    reminders = relationship("Reminder", back_populates="recurring_rule")
