"""recurring reminders

Revision ID: 0016_recurring_reminders
Revises: 0015_call_prefs_smart_voice
Create Date: 2026-06-08 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0016_recurring_reminders"
down_revision = "0015_call_prefs_smart_voice"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())

    if "recurring_reminder_rules" not in tables:
        op.create_table(
            "recurring_reminder_rules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("timezone", sa.String(length=100), nullable=False),
            sa.Column("repeat_type", sa.String(length=50), nullable=False),
            sa.Column("interval_value", sa.Integer(), nullable=True),
            sa.Column("interval_unit", sa.String(length=20), nullable=True),
            sa.Column("days_of_week", sa.Text(), nullable=True),
            sa.Column("day_of_month", sa.Integer(), nullable=True),
            sa.Column("time_of_day", sa.String(length=5), nullable=True),
            sa.Column("start_date", sa.Date(), nullable=True),
            sa.Column("end_date", sa.Date(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_generated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("next_occurrence_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("source_type", sa.String(length=50), nullable=True),
            sa.Column("email_message_id", sa.Integer(), nullable=True),
            sa.Column("email_summary_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_recurring_reminder_rules_user_id", "recurring_reminder_rules", ["user_id"])
        op.create_index("ix_recurring_reminder_rules_repeat_type", "recurring_reminder_rules", ["repeat_type"])
        op.create_index("ix_recurring_reminder_rules_next_occurrence_at", "recurring_reminder_rules", ["next_occurrence_at"])

    reminder_columns = {column["name"] for column in inspector.get_columns("reminders")} if "reminders" in tables else set()
    if "recurring_rule_id" not in reminder_columns:
        op.add_column("reminders", sa.Column("recurring_rule_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_reminders_recurring_rule_id", "reminders", "recurring_reminder_rules", ["recurring_rule_id"], ["id"])
    existing_indexes = {index["name"] for index in inspector.get_indexes("reminders")} if "reminders" in tables else set()
    if "ix_reminders_recurring_rule_id" not in existing_indexes:
        op.create_index("ix_reminders_recurring_rule_id", "reminders", ["recurring_rule_id"])
    if "uq_reminders_recurring_rule_occurrence" not in existing_indexes:
        op.create_index("uq_reminders_recurring_rule_occurrence", "reminders", ["recurring_rule_id", "reminder_at"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_reminders_recurring_rule_occurrence", table_name="reminders")
    op.drop_index("ix_reminders_recurring_rule_id", table_name="reminders")
    op.drop_constraint("fk_reminders_recurring_rule_id", "reminders", type_="foreignkey")
    op.drop_column("reminders", "recurring_rule_id")
    op.drop_index("ix_recurring_reminder_rules_next_occurrence_at", table_name="recurring_reminder_rules")
    op.drop_index("ix_recurring_reminder_rules_repeat_type", table_name="recurring_reminder_rules")
    op.drop_index("ix_recurring_reminder_rules_user_id", table_name="recurring_reminder_rules")
    op.drop_table("recurring_reminder_rules")
