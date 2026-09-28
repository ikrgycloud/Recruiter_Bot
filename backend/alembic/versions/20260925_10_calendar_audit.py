"""Keep the calendar event and scheduled range for approved requests."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20260925_10"
down_revision = "20260925_09"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("email_messages")}
    if "calendar_event_id" not in columns:
        op.add_column("email_messages", sa.Column("calendar_event_id", sa.String(length=255), nullable=True))
    if "scheduled_start" not in columns:
        op.add_column("email_messages", sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=True))
    if "scheduled_end" not in columns:
        op.add_column("email_messages", sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("email_messages", "scheduled_end")
    op.drop_column("email_messages", "scheduled_start")
    op.drop_column("email_messages", "calendar_event_id")
