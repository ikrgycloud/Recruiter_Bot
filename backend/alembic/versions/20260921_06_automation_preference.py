"""Add per-user approval-first rescheduling preference."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = "20260921_06"
down_revision = "20260918_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "automation_preferences" not in inspect(op.get_bind()).get_table_names():
        op.create_table(
            "automation_preferences",
            sa.Column("user_id", postgresql.UUID(as_uuid=True),
                      sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("automatic_rescheduling_enabled", sa.Boolean(), nullable=False,
                      server_default=sa.false()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.func.now()),
        )


def downgrade() -> None:
    if "automation_preferences" in inspect(op.get_bind()).get_table_names():
        op.drop_table("automation_preferences")
