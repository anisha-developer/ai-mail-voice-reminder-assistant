"""add priority contacts and priority mail alert logs

Revision ID: 0021_priority_contacts
Revises: 0020_call_pref_phone_number
Create Date: 2026-06-20 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0021_priority_contacts"
down_revision = "0020_call_pref_phone_number"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "priority_contacts",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("email_address", sa.String(length=255), nullable=False),
        sa.Column("relationship", sa.String(length=100), nullable=True),
        sa.Column("priority_level", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("user_id", "email_address", name="uq_priority_contacts_user_email_address"),
    )
    op.create_index("ix_priority_contacts_user_id", "priority_contacts", ["user_id"], unique=False)
    op.create_index("ix_priority_contacts_email_address", "priority_contacts", ["email_address"], unique=False)

    op.create_table(
        "priority_mail_alert_logs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("email_message_id", sa.Integer(), sa.ForeignKey("email_messages.id"), nullable=False),
        sa.Column("priority_contact_id", sa.Integer(), sa.ForeignKey("priority_contacts.id"), nullable=True),
        sa.Column("mail_call_log_id", sa.Integer(), sa.ForeignKey("mail_summary_call_logs.id"), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="triggered"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("email_message_id", name="uq_priority_mail_alert_logs_email_message_id"),
    )
    op.create_index("ix_priority_mail_alert_logs_user_id", "priority_mail_alert_logs", ["user_id"], unique=False)
    op.create_index("ix_priority_mail_alert_logs_email_message_id", "priority_mail_alert_logs", ["email_message_id"], unique=False)
    op.create_index("ix_priority_mail_alert_logs_priority_contact_id", "priority_mail_alert_logs", ["priority_contact_id"], unique=False)
    op.create_index("ix_priority_mail_alert_logs_mail_call_log_id", "priority_mail_alert_logs", ["mail_call_log_id"], unique=False)
    op.create_index("ix_priority_mail_alert_logs_status", "priority_mail_alert_logs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_priority_mail_alert_logs_status", table_name="priority_mail_alert_logs")
    op.drop_index("ix_priority_mail_alert_logs_mail_call_log_id", table_name="priority_mail_alert_logs")
    op.drop_index("ix_priority_mail_alert_logs_priority_contact_id", table_name="priority_mail_alert_logs")
    op.drop_index("ix_priority_mail_alert_logs_email_message_id", table_name="priority_mail_alert_logs")
    op.drop_index("ix_priority_mail_alert_logs_user_id", table_name="priority_mail_alert_logs")
    op.drop_table("priority_mail_alert_logs")

    op.drop_index("ix_priority_contacts_email_address", table_name="priority_contacts")
    op.drop_index("ix_priority_contacts_user_id", table_name="priority_contacts")
    op.drop_table("priority_contacts")
