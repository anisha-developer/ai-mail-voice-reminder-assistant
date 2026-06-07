from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class EmailMessage(Base):
    __tablename__ = "email_messages"
    __table_args__ = (UniqueConstraint("user_id", "gmail_message_id", name="uq_email_messages_user_gmail_message_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    gmail_message_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    gmail_thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    sender: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recipient: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    plain_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    html_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    has_attachments: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attachment_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read_from_gmail: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_summarized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)

    user = relationship("User", back_populates="email_messages")
