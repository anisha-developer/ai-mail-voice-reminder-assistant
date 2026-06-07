from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class VoiceCallInteraction(Base):
    __tablename__ = "voice_call_interactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    mail_call_log_id: Mapped[int] = mapped_column(ForeignKey("mail_summary_call_logs.id"), nullable=False, index=True)
    provider_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    interaction_order: Mapped[int] = mapped_column(Integer, nullable=False)
    user_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_intent: Mapped[str] = mapped_column(String(50), nullable=False)
    email_reference: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(50), nullable=True)
    system_response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)

    user = relationship("User", back_populates="voice_call_interactions")
    mail_call_log = relationship("MailSummaryCallLog", back_populates="voice_call_interactions")
