"""add phone number to user call preferences

Revision ID: 0020_call_pref_phone_number
Revises: 0019_gmail_connections_active_unique
Create Date: 2026-06-17 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0020_call_pref_phone_number"
down_revision = "0019_gmail_connections_active_uq"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_call_preferences", sa.Column("phone_number", sa.String(length=50), nullable=True))
    op.execute(
        """
        UPDATE user_call_preferences
        SET phone_number = users.phone_number
        FROM users
        WHERE user_call_preferences.user_id = users.id
          AND user_call_preferences.phone_number IS NULL
          AND users.phone_number IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_column("user_call_preferences", "phone_number")
