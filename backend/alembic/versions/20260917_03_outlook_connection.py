"""Add Outlook OAuth connections owned by application users."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect


revision = "20260917_03"
down_revision = "20260916_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "outlook_connections" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "outlook_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("token_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    if "outlook_connections" in inspect(op.get_bind()).get_table_names():
        op.drop_table("outlook_connections")