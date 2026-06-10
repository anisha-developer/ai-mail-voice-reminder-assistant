from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class UserCallPreference(Base):
    __tablename__ = "user_call_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True, index=True)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False, default="Asia/Kolkata")
    call_slot_1_time: Mapped[str] = mapped_column(String(5), nullable=False, default="09:00")
    call_slot_1_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    call_slot_2_time: Mapped[str] = mapped_column(String(5), nullable=False, default="13:00")
    call_slot_2_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    call_slot_3_time: Mapped[str] = mapped_column(String(5), nullable=False, default="19:00")
    call_slot_3_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    minimum_new_emails_to_call: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    skip_if_no_new_emails: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    avoid_repeating_delivered_emails: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)

    user = relationship("User", back_populates="call_preferences")
