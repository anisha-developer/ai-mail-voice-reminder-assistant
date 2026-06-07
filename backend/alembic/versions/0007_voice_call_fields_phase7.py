"""voice call fields phase 7

Revision ID: 0007_voice_call_fields_phase7
Revises: 0006_mail_summary_calls_phase6
Create Date: 2026-06-05 20:45:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_voice_call_fields_phase7"
down_revision = "0006_mail_summary_calls_phase6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mail_summary_call_logs", sa.Column("provider", sa.String(length=50), nullable=True))
    op.add_column("mail_summary_call_logs", sa.Column("provider_call_id", sa.String(length=255), nullable=True))
    op.add_column("mail_summary_call_logs", sa.Column("to_phone_number", sa.String(length=50), nullable=True))
    op.add_column("mail_summary_call_logs", sa.Column("from_phone_number", sa.String(length=50), nullable=True))
    op.add_column("mail_summary_call_logs", sa.Column("call_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mail_summary_call_logs", sa.Column("call_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("mail_summary_call_logs", sa.Column("call_duration_seconds", sa.Integer(), nullable=True))
    op.add_column("mail_summary_call_logs", sa.Column("provider_status", sa.String(length=50), nullable=True))
    op.add_column("mail_summary_call_logs", sa.Column("provider_error_message", sa.Text(), nullable=True))
    op.create_index(op.f("ix_mail_summary_call_logs_provider_call_id"), "mail_summary_call_logs", ["provider_call_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_mail_summary_call_logs_provider_call_id"), table_name="mail_summary_call_logs")
    op.drop_column("mail_summary_call_logs", "provider_error_message")
    op.drop_column("mail_summary_call_logs", "provider_status")
    op.drop_column("mail_summary_call_logs", "call_duration_seconds")
    op.drop_column("mail_summary_call_logs", "call_completed_at")
    op.drop_column("mail_summary_call_logs", "call_started_at")
    op.drop_column("mail_summary_call_logs", "from_phone_number")
    op.drop_column("mail_summary_call_logs", "to_phone_number")
    op.drop_column("mail_summary_call_logs", "provider_call_id")
    op.drop_column("mail_summary_call_logs", "provider")
