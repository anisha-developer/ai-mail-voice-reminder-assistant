"""expand email summaries for phase 5

Revision ID: 0005_email_summaries_phase5
Revises: 0004_email_messages_sync_fields
Create Date: 2026-06-05 00:00:04.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_email_summaries_phase5"
down_revision = "0004_email_messages_sync_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("email_summaries", sa.Column("email_message_id", sa.Integer(), nullable=True))
    op.add_column("email_summaries", sa.Column("sender", sa.String(length=255), nullable=True))
    op.add_column("email_summaries", sa.Column("subject", sa.String(length=255), nullable=True))
    op.add_column("email_summaries", sa.Column("short_summary", sa.Text(), nullable=True))
    op.add_column("email_summaries", sa.Column("detailed_summary", sa.Text(), nullable=True))
    op.add_column("email_summaries", sa.Column("action_required_text", sa.Text(), nullable=True))
    op.add_column("email_summaries", sa.Column("attachment_note", sa.Text(), nullable=True))
    op.add_column("email_summaries", sa.Column("summary_status", sa.String(length=50), server_default="completed", nullable=False))
    op.add_column("email_summaries", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column("email_summaries", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
    op.add_column("email_summaries", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
    op.create_foreign_key("fk_email_summaries_email_message_id", "email_summaries", "email_messages", ["email_message_id"], ["id"])
    op.create_unique_constraint("uq_email_summaries_email_message_id", "email_summaries", ["email_message_id"])

    op.execute("UPDATE email_summaries SET short_summary = summary_text WHERE short_summary IS NULL")
    op.execute("UPDATE email_summaries SET summary_status = 'completed' WHERE summary_status IS NULL")
    op.execute("UPDATE email_summaries SET email_message_id = 1 WHERE id = 1 AND email_message_id IS NULL")

    op.drop_column("email_summaries", "summary_text")
    op.drop_column("email_summaries", "summary_date")
    op.drop_column("email_summaries", "source_count")
    op.alter_column("email_summaries", "email_message_id", nullable=False)


def downgrade() -> None:
    op.add_column("email_summaries", sa.Column("source_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("email_summaries", sa.Column("summary_date", sa.Text(), nullable=True))
    op.add_column("email_summaries", sa.Column("summary_text", sa.Text(), nullable=False, server_default=""))
    op.execute("UPDATE email_summaries SET summary_text = COALESCE(short_summary, '')")

    op.drop_constraint("uq_email_summaries_email_message_id", "email_summaries", type_="unique")
    op.drop_constraint("fk_email_summaries_email_message_id", "email_summaries", type_="foreignkey")
    op.drop_column("email_summaries", "updated_at")
    op.drop_column("email_summaries", "created_at")
    op.drop_column("email_summaries", "error_message")
    op.drop_column("email_summaries", "summary_status")
    op.drop_column("email_summaries", "attachment_note")
    op.drop_column("email_summaries", "action_required_text")
    op.drop_column("email_summaries", "detailed_summary")
    op.drop_column("email_summaries", "short_summary")
    op.drop_column("email_summaries", "subject")
    op.drop_column("email_summaries", "sender")
    op.drop_column("email_summaries", "email_message_id")
