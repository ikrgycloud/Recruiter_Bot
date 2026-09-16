from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.dependencies import DbSession, get_current_user
from app.models.agent import Agent
from app.models.email_message import EmailMessage
from app.models.google_connection import GoogleConnection
from app.models.user import User

router = APIRouter()


@router.get("/overview")
async def overview(session: DbSession, user: User = Depends(get_current_user)) -> dict:
    agent_rows = await session.scalars(select(Agent).where(Agent.company_id == user.company_id)
                                       .order_by(Agent.last_seen_at.desc()))
    agents = [{
        "id": str(agent.id), "device_name": agent.device_name, "platform": agent.platform,
        "version": agent.version, "status": agent.status, "last_seen_at": agent.last_seen_at,
        "mailbox_email": agent.mailbox_email, "mailbox_connected": agent.mailbox_connected,
    } for agent in agent_rows]
    email_count = await session.scalar(select(func.count(EmailMessage.id)).where(EmailMessage.user_id == user.id))
    reschedule_count = await session.scalar(select(func.count(EmailMessage.id)).where(
        EmailMessage.user_id == user.id, EmailMessage.classification == "reschedule_request"))
    google_connected = await session.scalar(select(GoogleConnection.id).where(GoogleConnection.user_id == user.id))
    return {
        "user": {"id": str(user.id), "full_name": user.full_name, "email": user.email,
                 "company_id": str(user.company_id), "role": user.role},
        "agents": agents,
        "metrics": {"email_count": email_count or 0, "reschedule_count": reschedule_count or 0,
                    "online_agents": sum(agent["status"] == "running" for agent in agents)},
        "google_connected": google_connected is not None,
    }