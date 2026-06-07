"""gmail auto sync status fields

Revision ID: 0009_gmail_auto_sync_status
Revises: 0008_voice_interactions
Create Date: 2026-06-06 15:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_gmail_auto_sync_status"
down_revision = "0008_voice_interactions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gmail_connections", sa.Column("last_auto_sync_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("gmail_connections", sa.Column("last_auto_sync_status", sa.String(length=50), nullable=True))
    op.add_column("gmail_connections", sa.Column("last_auto_sync_error", sa.Text(), nullable=True))
    op.add_column("gmail_connections", sa.Column("last_auto_sync_inserted_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("gmail_connections", "last_auto_sync_inserted_count")
    op.drop_column("gmail_connections", "last_auto_sync_error")
    op.drop_column("gmail_connections", "last_auto_sync_status")
    op.drop_column("gmail_connections", "last_auto_sync_at")
