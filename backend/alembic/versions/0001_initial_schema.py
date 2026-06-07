"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-06-05 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("hashed_password", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("preferred_call_time", sa.String(length=50), nullable=True),
        sa.Column("timezone", sa.String(length=100), nullable=True),
        sa.Column("email_summary_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("voice_reminders_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(op.f("ix_user_preferences_id"), "user_preferences", ["id"], unique=False)
    op.create_index(op.f("ix_user_preferences_user_id"), "user_preferences", ["user_id"], unique=False)

    op.create_table(
        "email_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("message_id", sa.String(length=255), nullable=True),
        sa.Column("sender", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("raw_payload", sa.Text(), nullable=True),
    )
    op.create_index(op.f("ix_email_messages_id"), "email_messages", ["id"], unique=False)
    op.create_index(op.f("ix_email_messages_user_id"), "email_messages", ["user_id"], unique=False)
    op.create_index(op.f("ix_email_messages_message_id"), "email_messages", ["message_id"], unique=False)

    op.create_table(
        "email_summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("summary_date", sa.Text(), nullable=True),
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index(op.f("ix_email_summaries_id"), "email_summaries", ["id"], unique=False)
    op.create_index(op.f("ix_email_summaries_user_id"), "email_summaries", ["user_id"], unique=False)

    op.create_table(
        "mail_summary_call_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("call_status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("call_outcome", sa.String(length=100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index(op.f("ix_mail_summary_call_logs_id"), "mail_summary_call_logs", ["id"], unique=False)
    op.create_index(op.f("ix_mail_summary_call_logs_user_id"), "mail_summary_call_logs", ["user_id"], unique=False)

    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schedule_time", sa.String(length=100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index(op.f("ix_reminders_id"), "reminders", ["id"], unique=False)
    op.create_index(op.f("ix_reminders_user_id"), "reminders", ["user_id"], unique=False)

    op.create_table(
        "reminder_call_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reminder_id", sa.Integer(), sa.ForeignKey("reminders.id"), nullable=True),
        sa.Column("call_status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index(op.f("ix_reminder_call_logs_id"), "reminder_call_logs", ["id"], unique=False)
    op.create_index(op.f("ix_reminder_call_logs_user_id"), "reminder_call_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_reminder_call_logs_reminder_id"), "reminder_call_logs", ["reminder_id"], unique=False)

    op.create_table(
        "action_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column("action_status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("details", sa.Text(), nullable=True),
    )
    op.create_index(op.f("ix_action_logs_id"), "action_logs", ["id"], unique=False)
    op.create_index(op.f("ix_action_logs_user_id"), "action_logs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_action_logs_user_id"), table_name="action_logs")
    op.drop_index(op.f("ix_action_logs_id"), table_name="action_logs")
    op.drop_table("action_logs")

    op.drop_index(op.f("ix_reminder_call_logs_reminder_id"), table_name="reminder_call_logs")
    op.drop_index(op.f("ix_reminder_call_logs_user_id"), table_name="reminder_call_logs")
    op.drop_index(op.f("ix_reminder_call_logs_id"), table_name="reminder_call_logs")
    op.drop_table("reminder_call_logs")

    op.drop_index(op.f("ix_reminders_user_id"), table_name="reminders")
    op.drop_index(op.f("ix_reminders_id"), table_name="reminders")
    op.drop_table("reminders")

    op.drop_index(op.f("ix_mail_summary_call_logs_user_id"), table_name="mail_summary_call_logs")
    op.drop_index(op.f("ix_mail_summary_call_logs_id"), table_name="mail_summary_call_logs")
    op.drop_table("mail_summary_call_logs")

    op.drop_index(op.f("ix_email_summaries_user_id"), table_name="email_summaries")
    op.drop_index(op.f("ix_email_summaries_id"), table_name="email_summaries")
    op.drop_table("email_summaries")

    op.drop_index(op.f("ix_email_messages_message_id"), table_name="email_messages")
    op.drop_index(op.f("ix_email_messages_user_id"), table_name="email_messages")
    op.drop_index(op.f("ix_email_messages_id"), table_name="email_messages")
    op.drop_table("email_messages")

    op.drop_index(op.f("ix_user_preferences_user_id"), table_name="user_preferences")
    op.drop_index(op.f("ix_user_preferences_id"), table_name="user_preferences")
    op.drop_table("user_preferences")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_table("users")

