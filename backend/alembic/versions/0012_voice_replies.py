"""voice reply sessions and actions

Revision ID: 0012_voice_replies
Revises: 0011_reminders
Create Date: 2026-06-06 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_voice_replies"
down_revision = "0011_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voice_reply_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("mail_call_log_id", sa.Integer(), sa.ForeignKey("mail_summary_call_logs.id"), nullable=False),
        sa.Column("email_message_id", sa.Integer(), sa.ForeignKey("email_messages.id"), nullable=True),
        sa.Column("email_summary_id", sa.Integer(), sa.ForeignKey("email_summaries.id"), nullable=True),
        sa.Column("target_email_reference", sa.Integer(), nullable=True),
        sa.Column("reply_body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="awaiting_body"),
        sa.Column("gmail_message_id", sa.String(length=255), nullable=True),
        sa.Column("gmail_thread_id", sa.String(length=255), nullable=True),
        sa.Column("to_email", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.create_index("ix_voice_reply_sessions_user_id", "voice_reply_sessions", ["user_id"])
    op.create_index("ix_voice_reply_sessions_mail_call_log_id", "voice_reply_sessions", ["mail_call_log_id"])
    op.create_index("ix_voice_reply_sessions_status", "voice_reply_sessions", ["status"])

    op.create_table(
        "email_reply_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("email_message_id", sa.Integer(), sa.ForeignKey("email_messages.id"), nullable=True),
        sa.Column("mail_call_log_id", sa.Integer(), sa.ForeignKey("mail_summary_call_logs.id"), nullable=True),
        sa.Column("voice_reply_session_id", sa.Integer(), sa.ForeignKey("voice_reply_sessions.id"), nullable=True),
        sa.Column("gmail_message_id", sa.String(length=255), nullable=True),
        sa.Column("gmail_thread_id", sa.String(length=255), nullable=True),
        sa.Column("reply_body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="drafted"),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_email_reply_actions_user_id", "email_reply_actions", ["user_id"])
    op.create_index("ix_email_reply_actions_status", "email_reply_actions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_email_reply_actions_status", table_name="email_reply_actions")
    op.drop_index("ix_email_reply_actions_user_id", table_name="email_reply_actions")
    op.drop_table("email_reply_actions")
    op.drop_index("ix_voice_reply_sessions_status", table_name="voice_reply_sessions")
    op.drop_index("ix_voice_reply_sessions_mail_call_log_id", table_name="voice_reply_sessions")
    op.drop_index("ix_voice_reply_sessions_user_id", table_name="voice_reply_sessions")
    op.drop_table("voice_reply_sessions")
