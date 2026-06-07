"""voice call interactions phase 8

Revision ID: 0008_voice_interactions
Revises: 0007_voice_call_fields_phase7
Create Date: 2026-06-06 11:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_voice_interactions"
down_revision = "0007_voice_call_fields_phase7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voice_call_interactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("mail_call_log_id", sa.Integer(), nullable=False),
        sa.Column("provider_call_id", sa.String(length=255), nullable=True),
        sa.Column("interaction_order", sa.Integer(), nullable=False),
        sa.Column("user_transcript", sa.Text(), nullable=True),
        sa.Column("detected_intent", sa.String(length=50), nullable=False),
        sa.Column("email_reference", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.String(length=50), nullable=True),
        sa.Column("system_response_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["mail_call_log_id"], ["mail_summary_call_logs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_voice_call_interactions_id"), "voice_call_interactions", ["id"], unique=False)
    op.create_index(op.f("ix_voice_call_interactions_mail_call_log_id"), "voice_call_interactions", ["mail_call_log_id"], unique=False)
    op.create_index(op.f("ix_voice_call_interactions_provider_call_id"), "voice_call_interactions", ["provider_call_id"], unique=False)
    op.create_index(op.f("ix_voice_call_interactions_user_id"), "voice_call_interactions", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_voice_call_interactions_user_id"), table_name="voice_call_interactions")
    op.drop_index(op.f("ix_voice_call_interactions_provider_call_id"), table_name="voice_call_interactions")
    op.drop_index(op.f("ix_voice_call_interactions_mail_call_log_id"), table_name="voice_call_interactions")
    op.drop_index(op.f("ix_voice_call_interactions_id"), table_name="voice_call_interactions")
    op.drop_table("voice_call_interactions")
