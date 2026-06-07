"""add gmail email sync fields

Revision ID: 0004_email_messages_sync_fields
Revises: 0003_gmail_connections
Create Date: 2026-06-05 00:00:03.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_email_messages_sync_fields"
down_revision = "0003_gmail_connections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("email_messages", "message_id", new_column_name="gmail_message_id")
    op.add_column("email_messages", sa.Column("gmail_thread_id", sa.String(length=255), nullable=True))
    op.add_column("email_messages", sa.Column("recipient", sa.String(length=255), nullable=True))
    op.add_column("email_messages", sa.Column("plain_body", sa.Text(), nullable=True))
    op.add_column("email_messages", sa.Column("html_body", sa.Text(), nullable=True))
    op.add_column("email_messages", sa.Column("received_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("email_messages", sa.Column("has_attachments", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("email_messages", sa.Column("attachment_metadata", sa.Text(), nullable=True))
    op.add_column("email_messages", sa.Column("is_read_from_gmail", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("email_messages", sa.Column("is_summarized", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column(
        "email_messages",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.add_column(
        "email_messages",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_unique_constraint("uq_email_messages_user_gmail_message_id", "email_messages", ["user_id", "gmail_message_id"])


def downgrade() -> None:
    op.drop_constraint("uq_email_messages_user_gmail_message_id", "email_messages", type_="unique")
    op.drop_column("email_messages", "updated_at")
    op.drop_column("email_messages", "created_at")
    op.drop_column("email_messages", "is_summarized")
    op.drop_column("email_messages", "is_read_from_gmail")
    op.drop_column("email_messages", "attachment_metadata")
    op.drop_column("email_messages", "has_attachments")
    op.drop_column("email_messages", "received_at")
    op.drop_column("email_messages", "html_body")
    op.drop_column("email_messages", "plain_body")
    op.drop_column("email_messages", "recipient")
    op.drop_column("email_messages", "gmail_thread_id")
    op.alter_column("email_messages", "gmail_message_id", new_column_name="message_id")

