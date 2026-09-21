"""Store recruiter work days and shift times."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260921_07"
down_revision = "20260921_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("automation_preferences")}
    if "working_days" not in columns:
        op.add_column("automation_preferences", sa.Column(
            "working_days", sa.JSON(), nullable=False,
            server_default=sa.text("'[0,1,2,3,4]'::json"),
        ))
    if "shift_start" not in columns:
        op.add_column("automation_preferences", sa.Column(
            "shift_start", sa.Time(), nullable=False, server_default=sa.text("'09:00:00'"),
        ))
    if "shift_end" not in columns:
        op.add_column("automation_preferences", sa.Column(
            "shift_end", sa.Time(), nullable=False, server_default=sa.text("'17:00:00'"),
        ))


def downgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("automation_preferences")}
    for name in ("shift_end", "shift_start", "working_days"):
        if name in columns:
            op.drop_column("automation_preferences", name)
