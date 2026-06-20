"""add voice email reply logs

Revision ID: 0022_voice_email_reply_logs
Revises: 0021_priority_contacts
Create Date: 2026-06-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0022_voice_email_reply_logs"
down_revision = "0021_priority_contacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voice_email_reply_logs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("mail_call_id", sa.String(length=50), nullable=True),
        sa.Column("call_id", sa.String(length=255), nullable=True),
        sa.Column("email_number", sa.Integer(), nullable=True),
        sa.Column("original_email_id", sa.Integer(), sa.ForeignKey("email_messages.id"), nullable=True),
        sa.Column("original_summary_id", sa.Integer(), sa.ForeignKey("email_summaries.id"), nullable=True),
        sa.Column("original_sender", sa.String(length=255), nullable=True),
        sa.Column("original_subject", sa.String(length=255), nullable=True),
        sa.Column("reply_text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="voice_call"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_voice_email_reply_logs_user_id", "voice_email_reply_logs", ["user_id"], unique=False)
    op.create_index("ix_voice_email_reply_logs_mail_call_id", "voice_email_reply_logs", ["mail_call_id"], unique=False)
    op.create_index("ix_voice_email_reply_logs_call_id", "voice_email_reply_logs", ["call_id"], unique=False)
    op.create_index("ix_voice_email_reply_logs_email_number", "voice_email_reply_logs", ["email_number"], unique=False)
    op.create_index("ix_voice_email_reply_logs_status", "voice_email_reply_logs", ["status"], unique=False)
    op.create_index("ix_voice_email_reply_logs_source", "voice_email_reply_logs", ["source"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_voice_email_reply_logs_source", table_name="voice_email_reply_logs")
    op.drop_index("ix_voice_email_reply_logs_status", table_name="voice_email_reply_logs")
    op.drop_index("ix_voice_email_reply_logs_email_number", table_name="voice_email_reply_logs")
    op.drop_index("ix_voice_email_reply_logs_call_id", table_name="voice_email_reply_logs")
    op.drop_index("ix_voice_email_reply_logs_mail_call_id", table_name="voice_email_reply_logs")
    op.drop_index("ix_voice_email_reply_logs_user_id", table_name="voice_email_reply_logs")
    op.drop_table("voice_email_reply_logs")
