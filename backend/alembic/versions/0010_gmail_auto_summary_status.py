"""gmail auto summary status fields

Revision ID: 0010_gmail_auto_summary_status
Revises: 0009_gmail_auto_sync_status
Create Date: 2026-06-06 11:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_gmail_auto_summary_status"
down_revision = "0009_gmail_auto_sync_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gmail_connections", sa.Column("last_auto_summary_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("gmail_connections", sa.Column("last_auto_summary_status", sa.String(length=50), nullable=True))
    op.add_column("gmail_connections", sa.Column("last_auto_summary_error", sa.Text(), nullable=True))
    op.add_column("gmail_connections", sa.Column("last_auto_summary_success_count", sa.Integer(), nullable=True))
    op.add_column("gmail_connections", sa.Column("last_auto_summary_failed_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("gmail_connections", "last_auto_summary_failed_count")
    op.drop_column("gmail_connections", "last_auto_summary_success_count")
    op.drop_column("gmail_connections", "last_auto_summary_error")
    op.drop_column("gmail_connections", "last_auto_summary_status")
    op.drop_column("gmail_connections", "last_auto_summary_at")
