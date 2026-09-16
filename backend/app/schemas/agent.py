from datetime import datetime
from pydantic import BaseModel, Field


class AgentRegisterRequest(BaseModel):
    device_name: str = Field(min_length=1, max_length=255)
    platform: str = Field(min_length=1, max_length=80)
    version: str = Field(default="0.1.0", max_length=40)


class AgentHeartbeatRequest(BaseModel):
    status: str = Field(default="running", pattern="^(running|idle|error|offline)$")
    version: str = Field(default="0.1.0", max_length=40)


class AgentResponse(BaseModel):
    id: str
    device_name: str
    platform: str
    version: str
    status: str
    last_seen_at: datetime | None
    mailbox_email: str | None = None
    mailbox_connected: bool = False
