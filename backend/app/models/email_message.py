import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmailMessage(Base):
    __tablename__ = "email_messages"
    __table_args__ = (UniqueConstraint("user_id", "provider_message_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider_message_id: Mapped[str] = mapped_column(String(255))
    thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender: Mapped[str | None] = mapped_column(String(500), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    body_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    classification: Mapped[str] = mapped_column(String(40), default="other")
    processed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())