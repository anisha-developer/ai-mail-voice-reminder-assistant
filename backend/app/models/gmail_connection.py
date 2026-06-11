from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class GmailConnection(Base):
    __tablename__ = "gmail_connections"
    __table_args__ = (
        Index(
            "uq_gmail_connections_user_active",
            "user_id",
            unique=True,
            postgresql_where=text("is_connected = true"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    gmail_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_uri: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    is_connected: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_auto_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_auto_sync_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_auto_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_auto_sync_inserted_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_auto_summary_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_auto_summary_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_auto_summary_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_auto_summary_success_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_auto_summary_failed_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user = relationship("User", back_populates="gmail_connections")
