"""Remove the retired desktop-agent table."""
from alembic import op
from sqlalchemy import inspect


revision = "20260917_04"
down_revision = "20260917_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "agents" in inspect(op.get_bind()).get_table_names():
        op.drop_table("agents")


def downgrade() -> None:
    raise NotImplementedError("The retired agents table is not restored by downgrade")
