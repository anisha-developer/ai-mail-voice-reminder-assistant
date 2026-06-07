"""reminders table refresh

Revision ID: 0011_reminders
Revises: 0010_gmail_auto_summary_status
Create Date: 2026-06-06 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_reminders"
down_revision = "0010_gmail_auto_summary_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("reminders") as batch:
        batch.drop_column("description")
        batch.drop_column("schedule_time")
        batch.drop_column("is_active")
        batch.add_column(sa.Column("notes", sa.Text(), nullable=True))
        batch.add_column(sa.Column("reminder_at", sa.DateTime(timezone=True), nullable=False))
        batch.add_column(sa.Column("timezone", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("phone_number", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("status", sa.String(length=50), nullable=False, server_default="scheduled"))
        batch.add_column(sa.Column("provider", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("provider_call_id", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("called_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("last_error", sa.Text(), nullable=True))
        batch.add_column(sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))

    op.create_index("ix_reminders_reminder_at", "reminders", ["reminder_at"])
    op.create_index("ix_reminders_status", "reminders", ["status"])
    op.create_index("ix_reminders_provider_call_id", "reminders", ["provider_call_id"])


def downgrade() -> None:
    op.drop_index("ix_reminders_provider_call_id", table_name="reminders")
    op.drop_index("ix_reminders_status", table_name="reminders")
    op.drop_index("ix_reminders_reminder_at", table_name="reminders")
    with op.batch_alter_table("reminders") as batch:
        batch.drop_column("updated_at")
        batch.drop_column("created_at")
        batch.drop_column("last_error")
        batch.drop_column("called_at")
        batch.drop_column("provider_call_id")
        batch.drop_column("provider")
        batch.drop_column("status")
        batch.drop_column("phone_number")
        batch.drop_column("timezone")
        batch.drop_column("reminder_at")
        batch.drop_column("notes")
        batch.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch.add_column(sa.Column("schedule_time", sa.String(length=100), nullable=True))
        batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
