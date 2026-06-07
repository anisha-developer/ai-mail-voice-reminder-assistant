from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    preferred_call_time: Mapped[str | None] = mapped_column(String(50), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preferred_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email_summary_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    voice_reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_mail_summary_calls_per_day: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    user = relationship("User", back_populates="preferences")
