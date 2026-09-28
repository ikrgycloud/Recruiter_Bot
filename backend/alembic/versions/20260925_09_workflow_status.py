"""Record workflow and confirmation email outcomes."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260925_09"
down_revision = "20260924_08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("email_messages")}
    if "workflow_status" not in columns:
        op.add_column("email_messages", sa.Column("workflow_status", sa.String(length=40), nullable=False,
                       server_default="pending"))
    if "notification_sent" not in columns:
        op.add_column("email_messages", sa.Column("notification_sent", sa.Boolean(), nullable=False,
                       server_default=sa.false()))
    if "failure_reason" not in columns:
        op.add_column("email_messages", sa.Column("failure_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("email_messages", "failure_reason")
    op.drop_column("email_messages", "notification_sent")
    op.drop_column("email_messages", "workflow_status")
