"""track whether synced emails are still present in the gmail inbox

Revision ID: 0018_email_messages_inbox_state
Revises: 0017_voice_recurring_reminder_support
Create Date: 2026-06-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_email_messages_inbox_state"
down_revision = "0017_voice_recurring_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_messages",
        sa.Column("is_in_inbox", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(op.f("ix_email_messages_is_in_inbox"), "email_messages", ["is_in_inbox"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_email_messages_is_in_inbox"), table_name="email_messages")
    op.drop_column("email_messages", "is_in_inbox")
