import platform
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.api.dependencies import DbSession, get_current_user
from app.models.agent import Agent
from app.models.user import User
from app.schemas.agent import AgentHeartbeatRequest, AgentRegisterRequest, AgentResponse

router = APIRouter()


def response(agent: Agent) -> AgentResponse:
    return AgentResponse(id=str(agent.id), device_name=agent.device_name, platform=agent.platform,
                         version=agent.version, status=agent.status, last_seen_at=agent.last_seen_at,
                         mailbox_email=agent.mailbox_email, mailbox_connected=agent.mailbox_connected)


@router.post("/register", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def register_agent(payload: AgentRegisterRequest, session: DbSession,
                         user: User = Depends(get_current_user)) -> AgentResponse:
    agent = Agent(company_id=user.company_id, device_name=payload.device_name,
                  platform=payload.platform, version=payload.version,
                  status="awaiting_mailbox", last_seen_at=datetime.now(timezone.utc))
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return response(agent)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: UUID, session: DbSession,
                    user: User = Depends(get_current_user)) -> AgentResponse:
    agent = await session.scalar(select(Agent).where(Agent.id == agent_id, Agent.company_id == user.company_id))
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return response(agent)


@router.post("/{agent_id}/heartbeat", response_model=AgentResponse)
async def heartbeat(agent_id: UUID, payload: AgentHeartbeatRequest, session: DbSession,
                    user: User = Depends(get_current_user)) -> AgentResponse:
    agent = await session.scalar(select(Agent).where(Agent.id == agent_id, Agent.company_id == user.company_id))
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    if not agent.mailbox_connected and payload.status == "running":
        agent.status = "awaiting_mailbox"
    else:
        agent.status = payload.status
    agent.version = payload.version
    agent.last_seen_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(agent)
    return response(agent)
