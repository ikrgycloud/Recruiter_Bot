"""Track the mailbox selected for each desktop agent."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260916_02"
down_revision = "20260916_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = inspect(op.get_bind()).get_table_names()
    if "agents" not in existing:
        return
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("agents")}
    if "mailbox_email" not in columns:
        op.add_column("agents", sa.Column("mailbox_email", sa.String(255), nullable=True))
    if "mailbox_connected" not in columns:
        op.add_column("agents", sa.Column("mailbox_connected", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    if "agents" not in inspect(op.get_bind()).get_table_names():
        return
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("agents")}
    if "mailbox_connected" in columns:
        op.drop_column("agents", "mailbox_connected")
    if "mailbox_email" in columns:
        op.drop_column("agents", "mailbox_email")