import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    device_name: Mapped[str] = mapped_column(String(255))
    platform: Mapped[str] = mapped_column(String(80))
    version: Mapped[str] = mapped_column(String(40), default="0.1.0")
    status: Mapped[str] = mapped_column(String(30), default="offline")
    mailbox_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mailbox_connected: Mapped[bool] = mapped_column(default=False, server_default="false")
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    company = relationship("Company", back_populates="agents")
