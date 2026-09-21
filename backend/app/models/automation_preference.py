import uuid
from datetime import datetime, time

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Time, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AutomationPreference(Base):
    __tablename__ = "automation_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    automatic_rescheduling_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    working_days: Mapped[list[int]] = mapped_column(
        JSON, nullable=False, default=lambda: [0, 1, 2, 3, 4],
        server_default='[0,1,2,3,4]',
    )
    shift_start: Mapped[time] = mapped_column(
        Time, nullable=False, default=time(9), server_default="09:00:00"
    )
    shift_end: Mapped[time] = mapped_column(
        Time, nullable=False, default=time(17), server_default="17:00:00"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
