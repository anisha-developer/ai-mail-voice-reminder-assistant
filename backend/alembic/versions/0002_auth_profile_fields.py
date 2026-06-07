"""add auth and profile fields

Revision ID: 0002_auth_profile_fields
Revises: 0001_initial_schema
Create Date: 2026-06-05 00:00:01.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_auth_profile_fields"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("users", "full_name", new_column_name="name")
    op.add_column("users", sa.Column("phone_number", sa.String(length=50), nullable=True))
    op.add_column("users", sa.Column("timezone", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("preferred_language", sa.String(length=50), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )

    op.add_column(
        "user_preferences",
        sa.Column("preferred_language", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "user_preferences",
        sa.Column("max_mail_summary_calls_per_day", sa.Integer(), server_default="3", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "max_mail_summary_calls_per_day")
    op.drop_column("user_preferences", "preferred_language")

    op.drop_column("users", "created_at")
    op.drop_column("users", "preferred_language")
    op.drop_column("users", "timezone")
    op.drop_column("users", "phone_number")
    op.alter_column("users", "name", new_column_name="full_name")
