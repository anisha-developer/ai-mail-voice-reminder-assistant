"""missed reminder recovery

Revision ID: 0014_missed_reminder_recovery
Revises: 0013_voice_reminder_sessions
Create Date: 2026-06-07 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0014_missed_reminder_recovery"
down_revision = "0013_voice_reminder_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("reminders")} if "reminders" in inspector.get_table_names() else set()

    if "retry_count" not in columns:
        op.add_column("reminders", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    if "max_retry_attempts" not in columns:
        op.add_column("reminders", sa.Column("max_retry_attempts", sa.Integer(), nullable=False, server_default="3"))
    if "next_retry_at" not in columns:
        op.add_column("reminders", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    if "last_call_status" not in columns:
        op.add_column("reminders", sa.Column("last_call_status", sa.String(length=50), nullable=True))
    if "completed_manually_at" not in columns:
        op.add_column("reminders", sa.Column("completed_manually_at", sa.DateTime(timezone=True), nullable=True))
    if "snoozed_until" not in columns:
        op.add_column("reminders", sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True))

    existing_indexes = {index["name"] for index in inspector.get_indexes("reminders")} if "reminders" in inspector.get_table_names() else set()
    if "ix_reminders_next_retry_at" not in existing_indexes:
        op.create_index("ix_reminders_next_retry_at", "reminders", ["next_retry_at"])
    if "ix_reminders_snoozed_until" not in existing_indexes:
        op.create_index("ix_reminders_snoozed_until", "reminders", ["snoozed_until"])
    if "ix_reminders_last_call_status" not in existing_indexes:
        op.create_index("ix_reminders_last_call_status", "reminders", ["last_call_status"])
    if "ix_reminders_completed_manually_at" not in existing_indexes:
        op.create_index("ix_reminders_completed_manually_at", "reminders", ["completed_manually_at"])


def downgrade() -> None:
    op.drop_index("ix_reminders_completed_manually_at", table_name="reminders")
    op.drop_index("ix_reminders_last_call_status", table_name="reminders")
    op.drop_index("ix_reminders_snoozed_until", table_name="reminders")
    op.drop_index("ix_reminders_next_retry_at", table_name="reminders")
    op.drop_column("reminders", "snoozed_until")
    op.drop_column("reminders", "completed_manually_at")
    op.drop_column("reminders", "last_call_status")
    op.drop_column("reminders", "next_retry_at")
    op.drop_column("reminders", "max_retry_attempts")
    op.drop_column("reminders", "retry_count")
