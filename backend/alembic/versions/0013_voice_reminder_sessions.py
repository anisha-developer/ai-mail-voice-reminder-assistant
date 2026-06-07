"""voice reminder sessions

Revision ID: 0013_voice_reminder_sessions
Revises: 0012_voice_replies
Create Date: 2026-06-06 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0013_voice_reminder_sessions"
down_revision = "0012_voice_replies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "voice_reminder_sessions" not in inspector.get_table_names():
        op.create_table(
            "voice_reminder_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("mail_call_log_id", sa.Integer(), sa.ForeignKey("mail_summary_call_logs.id"), nullable=False),
            sa.Column("email_message_id", sa.Integer(), sa.ForeignKey("email_messages.id"), nullable=True),
            sa.Column("email_summary_id", sa.Integer(), sa.ForeignKey("email_summaries.id"), nullable=True),
            sa.Column("target_email_reference", sa.Integer(), nullable=True),
            sa.Column("reminder_title", sa.String(length=255), nullable=True),
            sa.Column("reminder_notes", sa.Text(), nullable=True),
            sa.Column("reminder_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reminder_timezone", sa.String(length=100), nullable=True),
            sa.Column("reminder_phone_number", sa.String(length=50), nullable=True),
            sa.Column("status", sa.String(length=50), nullable=False, server_default="awaiting_details"),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("created_reminder_id", sa.Integer(), sa.ForeignKey("reminders.id"), nullable=True),
        )
    existing_indexes = {index["name"] for index in inspector.get_indexes("voice_reminder_sessions")} if "voice_reminder_sessions" in inspector.get_table_names() else set()
    if "ix_voice_reminder_sessions_user_id" not in existing_indexes:
        op.create_index("ix_voice_reminder_sessions_user_id", "voice_reminder_sessions", ["user_id"])
    if "ix_voice_reminder_sessions_mail_call_log_id" not in existing_indexes:
        op.create_index("ix_voice_reminder_sessions_mail_call_log_id", "voice_reminder_sessions", ["mail_call_log_id"])
    if "ix_voice_reminder_sessions_status" not in existing_indexes:
        op.create_index("ix_voice_reminder_sessions_status", "voice_reminder_sessions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_voice_reminder_sessions_status", table_name="voice_reminder_sessions")
    op.drop_index("ix_voice_reminder_sessions_mail_call_log_id", table_name="voice_reminder_sessions")
    op.drop_index("ix_voice_reminder_sessions_user_id", table_name="voice_reminder_sessions")
    op.drop_table("voice_reminder_sessions")
