from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)

    preferences = relationship("UserPreference", back_populates="user", cascade="all, delete-orphan")
    email_messages = relationship("EmailMessage", back_populates="user", cascade="all, delete-orphan")
    email_summaries = relationship("EmailSummary", back_populates="user", cascade="all, delete-orphan")
    mail_summary_call_logs = relationship("MailSummaryCallLog", back_populates="user", cascade="all, delete-orphan")
    reminders = relationship("Reminder", back_populates="user", cascade="all, delete-orphan")
    reminder_call_logs = relationship("ReminderCallLog", back_populates="user", cascade="all, delete-orphan")
    recurring_reminder_rules = relationship("RecurringReminderRule", back_populates="user", cascade="all, delete-orphan")
    action_logs = relationship("ActionLog", back_populates="user", cascade="all, delete-orphan")
    gmail_connections = relationship("GmailConnection", back_populates="user", cascade="all, delete-orphan")
    voice_call_interactions = relationship("VoiceCallInteraction", back_populates="user", cascade="all, delete-orphan")
    call_preferences = relationship("UserCallPreference", back_populates="user", cascade="all, delete-orphan")
    priority_contacts = relationship("PriorityContact", back_populates="user", cascade="all, delete-orphan")
    priority_mail_alert_logs = relationship("PriorityMailAlertLog", back_populates="user", cascade="all, delete-orphan")
