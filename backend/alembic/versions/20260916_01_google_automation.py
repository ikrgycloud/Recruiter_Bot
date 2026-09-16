"""Add roles, Google connections, and synced email messages."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

revision = "20260916_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(30) NOT NULL DEFAULT 'recruiter'")
    existing = inspect(op.get_bind()).get_table_names()
    if "google_connections" not in existing:
        op.create_table(
            "google_connections",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
            sa.Column("email", sa.String(255), nullable=True), sa.Column("token_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    if "email_messages" not in existing:
        op.create_table(
            "email_messages",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("provider_message_id", sa.String(255), nullable=False), sa.Column("thread_id", sa.String(255)),
            sa.Column("sender", sa.String(500)), sa.Column("subject", sa.String(500)), sa.Column("body_preview", sa.Text()),
            sa.Column("received_at", sa.DateTime(timezone=True)), sa.Column("classification", sa.String(40), nullable=False, server_default="other"),
            sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "provider_message_id"),
        )


def downgrade() -> None:
    existing = inspect(op.get_bind()).get_table_names()
    if "email_messages" in existing:
        op.drop_table("email_messages")
    if "google_connections" in existing:
        op.drop_table("google_connections")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS role")
