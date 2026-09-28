"""Track the provider that owns each synced email."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260924_08"
down_revision = "20260921_07"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("email_messages")}
    if "provider" not in columns:
        op.add_column("email_messages", sa.Column("provider", sa.String(length=20), nullable=False,
                       server_default="google"))
        op.create_index("ix_email_messages_provider", "email_messages", ["provider"])


def downgrade() -> None:
    op.drop_index("ix_email_messages_provider", table_name="email_messages")
    op.drop_column("email_messages", "provider")
