"""Track initial and incremental Gmail inbox sync state."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision = "20260918_05"
down_revision = "20260917_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "mailbox_sync_states" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "mailbox_sync_states",
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("initial_sync_complete", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    if "mailbox_sync_states" in inspect(op.get_bind()).get_table_names():
        op.drop_table("mailbox_sync_states")
