"""mail summary calls phase 6

Revision ID: 0006_mail_summary_calls_phase6
Revises: 0005_email_summaries_phase5
Create Date: 2026-06-05 18:55:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_mail_summary_calls_phase6"
down_revision = "0005_email_summaries_phase5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("email_summaries", sa.Column("is_delivered_in_mail_call", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("email_summaries", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("email_summaries", sa.Column("mail_call_log_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_email_summaries_mail_call_log_id"), "email_summaries", ["mail_call_log_id"], unique=False)
    op.create_foreign_key(
        "fk_email_summaries_mail_call_log_id_mail_summary_call_logs",
        "email_summaries",
        "mail_summary_call_logs",
        ["mail_call_log_id"],
        ["id"],
    )
    op.alter_column("email_summaries", "is_delivered_in_mail_call", server_default=None)

    op.add_column("mail_summary_call_logs", sa.Column("call_type", sa.String(length=50), nullable=False, server_default="mail_summary"))
    op.add_column("mail_summary_call_logs", sa.Column("call_date", sa.Date(), nullable=True))
    op.add_column("mail_summary_call_logs", sa.Column("call_time", sa.Time(), nullable=True))
    op.add_column("mail_summary_call_logs", sa.Column("summary_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("mail_summary_call_logs", sa.Column("script_text", sa.Text(), nullable=True))
    op.add_column("mail_summary_call_logs", sa.Column("delivery_status", sa.String(length=50), nullable=False, server_default="pending"))
    op.add_column("mail_summary_call_logs", sa.Column("delivered_summary_ids", sa.Text(), nullable=True))
    op.add_column("mail_summary_call_logs", sa.Column("failure_reason", sa.Text(), nullable=True))
    op.add_column("mail_summary_call_logs", sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))
    op.add_column("mail_summary_call_logs", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")))

    op.execute("UPDATE mail_summary_call_logs SET call_type = 'mail_summary' WHERE call_type IS NULL")
    op.execute("UPDATE mail_summary_call_logs SET call_status = COALESCE(call_status, 'prepared')")
    op.execute("UPDATE mail_summary_call_logs SET delivery_status = 'pending' WHERE delivery_status IS NULL")
    op.execute("UPDATE mail_summary_call_logs SET summary_count = 0 WHERE summary_count IS NULL")
    op.execute("UPDATE mail_summary_call_logs SET call_date = CURRENT_DATE WHERE call_date IS NULL")
    op.execute("UPDATE mail_summary_call_logs SET call_time = CURRENT_TIME WHERE call_time IS NULL")

    op.alter_column("mail_summary_call_logs", "call_type", server_default=None)
    op.alter_column("mail_summary_call_logs", "summary_count", server_default=None)
    op.alter_column("mail_summary_call_logs", "delivery_status", server_default=None)
    op.alter_column("mail_summary_call_logs", "call_date", nullable=False)
    op.alter_column("mail_summary_call_logs", "call_time", nullable=False)

    with op.batch_alter_table("mail_summary_call_logs") as batch_op:
        batch_op.drop_column("call_outcome")
        batch_op.drop_column("notes")

    op.create_index(op.f("ix_mail_summary_call_logs_call_date"), "mail_summary_call_logs", ["call_date"], unique=False)
    op.create_index(op.f("ix_mail_summary_call_logs_call_status"), "mail_summary_call_logs", ["call_status"], unique=False)
    op.create_index(op.f("ix_mail_summary_call_logs_call_type"), "mail_summary_call_logs", ["call_type"], unique=False)
    op.create_index(op.f("ix_mail_summary_call_logs_delivery_status"), "mail_summary_call_logs", ["delivery_status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_mail_summary_call_logs_delivery_status"), table_name="mail_summary_call_logs")
    op.drop_index(op.f("ix_mail_summary_call_logs_call_type"), table_name="mail_summary_call_logs")
    op.drop_index(op.f("ix_mail_summary_call_logs_call_status"), table_name="mail_summary_call_logs")
    op.drop_index(op.f("ix_mail_summary_call_logs_call_date"), table_name="mail_summary_call_logs")

    op.add_column("mail_summary_call_logs", sa.Column("notes", sa.TEXT(), autoincrement=False, nullable=True))
    op.add_column("mail_summary_call_logs", sa.Column("call_outcome", sa.VARCHAR(length=100), autoincrement=False, nullable=True))

    op.drop_column("mail_summary_call_logs", "updated_at")
    op.drop_column("mail_summary_call_logs", "created_at")
    op.drop_column("mail_summary_call_logs", "failure_reason")
    op.drop_column("mail_summary_call_logs", "delivered_summary_ids")
    op.drop_column("mail_summary_call_logs", "delivery_status")
    op.drop_column("mail_summary_call_logs", "script_text")
    op.drop_column("mail_summary_call_logs", "summary_count")
    op.drop_column("mail_summary_call_logs", "call_time")
    op.drop_column("mail_summary_call_logs", "call_date")
    op.drop_column("mail_summary_call_logs", "call_type")

    op.drop_constraint("fk_email_summaries_mail_call_log_id_mail_summary_call_logs", "email_summaries", type_="foreignkey")
    op.drop_index(op.f("ix_email_summaries_mail_call_log_id"), table_name="email_summaries")
    op.drop_column("email_summaries", "mail_call_log_id")
    op.drop_column("email_summaries", "delivered_at")
    op.drop_column("email_summaries", "is_delivered_in_mail_call")
