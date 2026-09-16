"""Track the mailbox selected for each desktop agent."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260916_02"
down_revision = "20260916_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("agents")}
    if "mailbox_email" not in columns:
        op.add_column("agents", sa.Column("mailbox_email", sa.String(255), nullable=True))
    if "mailbox_connected" not in columns:
        op.add_column("agents", s