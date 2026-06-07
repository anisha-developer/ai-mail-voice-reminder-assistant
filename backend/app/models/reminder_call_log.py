from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class ReminderCallLog(Base):
    __tablename__ = "reminder_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    reminder_id: Mapped[int | None] = mapped_column(ForeignKey("reminders.id"), nullable=True, index=True)
    call_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="reminder_call_logs")

