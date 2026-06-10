"""voice recurring reminder support

Revision ID: 0017_voice_recurring_reminder_support
Revises: 0016_recurring_reminders
Create Date: 2026-06-08 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0017_voice_recurring_support"
down_revision = "0016_recurring_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "voice_reminder_sessions" in tables:
        columns = {column["name"] for column in inspector.get_columns("voice_reminder_sessions")}
        if "repeat_type" not in columns:
            op.add_column("voice_reminder_sessions", sa.Column("repeat_type", sa.String(length=50), nullable=True))
        if "interval_value" not in columns:
            op.add_column("voice_reminder_sessions", sa.Column("interval_value", sa.Integer(), nullable=True))
        if "interval_unit" not in columns:
            op.add_column("voice_reminder_sessions", sa.Column("interval_unit", sa.String(length=20), nullable=True))
        if "days_of_week" not in columns:
            op.add_column("voice_reminder_sessions", sa.Column("days_of_week", sa.Text(), nullable=True))
        if "day_of_month" not in columns:
            op.add_column("voice_reminder_sessions", sa.Column("day_of_month", sa.Integer(), nullable=True))
        if "time_of_day" not in columns:
            op.add_column("voice_reminder_sessions", sa.Column("time_of_day", sa.String(length=5), nullable=True))
        if "start_date" not in columns:
            op.add_column("voice_reminder_sessions", sa.Column("start_date", sa.String(length=20), nullable=True))
        if "end_date" not in columns:
            op.add_column("voice_reminder_sessions", sa.Column("end_date", sa.String(length=20), nullable=True))
        if "created_recurring_rule_id" not in columns:
            op.add_column("voice_reminder_sessions", sa.Column("created_recurring_rule_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_voice_reminder_sessions_created_recurring_rule_id",
                "voice_reminder_sessions",
                "recurring_reminder_rules",
                ["created_recurring_rule_id"],
                ["id"],
            )


def downgrade() -> None:
    op.drop_constraint("fk_voice_reminder_sessions_created_recurring_rule_id", "voice_reminder_sessions", type_="foreignkey")
    op.drop_column("voice_reminder_sessions", "created_recurring_rule_id")
    op.drop_column("voice_reminder_sessions", "end_date")
    op.drop_column("voice_reminder_sessions", "start_date")
    op.drop_column("voice_reminder_sessions", "time_of_day")
    op.drop_column("voice_reminder_sessions", "day_of_month")
    op.drop_column("voice_reminder_sessions", "days_of_week")
    op.drop_column("voice_reminder_sessions", "interval_unit")
    op.drop_column("voice_reminder_sessions", "interval_value")
    op.drop_column("voice_reminder_sessions", "repeat_type")
