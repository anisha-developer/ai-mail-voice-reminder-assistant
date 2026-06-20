from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


class PriorityMailAlertLog(Base):
    __tablename__ = "priority_mail_alert_logs"
    __table_args__ = (UniqueConstraint("email_message_id", name="uq_priority_mail_alert_logs_email_message_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    email_message_id: Mapped[int] = mapped_column(ForeignKey("email_messages.id"), nullable=False, index=True)
    priority_contact_id: Mapped[int | None] = mapped_column(ForeignKey("priority_contacts.id"), nullable=True, index=True)
    mail_call_log_id: Mapped[int | None] = mapped_column(ForeignKey("mail_summary_call_logs.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="triggered", nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)

    user = relationship("User", back_populates="priority_mail_alert_logs")
    email_message = relationship("EmailMessage")
    priority_contact = relationship("PriorityContact")
    mail_call_log = relationship("MailSummaryCallLog")
