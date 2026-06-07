from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class ActionLog(Base):
    __tablename__ = "action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    action_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="action_logs")

