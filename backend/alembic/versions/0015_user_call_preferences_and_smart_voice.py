"""user call preferences and smart voice support

Revision ID: 0015_call_prefs_smart_voice
Revises: 0014_missed_reminder_recovery
Create Date: 2026-06-07 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0015_call_prefs_smart_voice"
down_revision = "0014_missed_reminder_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    if "user_call_preferences" not in tables:
        op.create_table(
            "user_call_preferences",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, unique=True),
            sa.Column("timezone", sa.String(length=100), nullable=False, server_default="Asia/Kolkata"),
            sa.Column("call_slot_1_time", sa.String(length=5), nullable=False, server_default="09:00"),
            sa.Column("call_slot_1_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("call_slot_2_time", sa.String(length=5), nullable=False, server_default="13:00"),
            sa.Column("call_slot_2_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("call_slot_3_time", sa.String(length=5), nullable=False, server_default="19:00"),
            sa.Column("call_slot_3_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("minimum_new_emails_to_call", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("skip_if_no_new_emails", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("avoid_repeating_delivered_emails", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_user_call_preferences_user_id", "user_call_preferences", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_call_preferences_user_id", table_name="user_call_preferences")
    op.drop_table("user_call_preferences")
