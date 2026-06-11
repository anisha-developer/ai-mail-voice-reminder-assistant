"""switch gmail connections uniqueness to active-only

Revision ID: 0019_gmail_connections_active_uq
Revises: 0018_email_messages_inbox_state
Create Date: 2026-06-11 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0019_gmail_connections_active_uq"
down_revision = "0018_email_messages_inbox_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_gmail_connections_user_active", "gmail_connections", type_="unique")
    op.create_index(
        "uq_gmail_connections_user_active",
        "gmail_connections",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_connected = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_gmail_connections_user_active", table_name="gmail_connections")
    op.create_unique_constraint(
        "uq_gmail_connections_user_active",
        "gmail_connections",
        ["user_id", "is_connected"],
    )
