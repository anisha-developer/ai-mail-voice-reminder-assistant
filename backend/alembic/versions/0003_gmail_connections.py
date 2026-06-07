"""gmail connections

Revision ID: 0003_gmail_connections
Revises: 0002_auth_profile_fields
Create Date: 2026-06-05 00:00:02.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_gmail_connections"
down_revision = "0002_auth_profile_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gmail_connections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("gmail_email", sa.String(length=255), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("token_uri", sa.String(length=255), nullable=True),
        sa.Column("scopes", sa.Text(), nullable=True),
        sa.Column("expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("is_connected", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(op.f("ix_gmail_connections_id"), "gmail_connections", ["id"], unique=False)
    op.create_index(op.f("ix_gmail_connections_user_id"), "gmail_connections", ["user_id"], unique=False)
    op.create_index(op.f("ix_gmail_connections_is_connected"), "gmail_connections", ["is_connected"], unique=False)
    op.create_unique_constraint("uq_gmail_connections_user_active", "gmail_connections", ["user_id", "is_connected"])


def downgrade() -> None:
    op.drop_constraint("uq_gmail_connections_user_active", "gmail_connections", type_="unique")
    op.drop_index(op.f("ix_gmail_connections_is_connected"), table_name="gmail_connections")
    op.drop_index(op.f("ix_gmail_connections_user_id"), table_name="gmail_connections")
    op.drop_index(op.f("ix_gmail_connections_id"), table_name="gmail_connections")
    op.drop_table("gmail_connections")
