from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.api.dependencies import DbSession, get_current_user
from app.models.email_message import EmailMessage
from app.models.google_connection import GoogleConnection
from app.models.user import User

router = APIRouter()


@router.get("/overview")
async def overview(session: DbSession, user: User = Depends(get_current_user)) -> dict:
    email_count = await session.scalar(select(func.count(EmailMessage.id)).where(EmailMessage.user_id == user.id))
    reschedule_count = await session.scalar(select(func.count(EmailMessage.id)).where(
        EmailMessage.user_id == user.id, EmailMessage.classification == "reschedule_request"))
    google_connected = await session.scalar(select(GoogleConnection.id).where(GoogleConnection.user_id == user.id))
    return {
        "user": {"id": str(user.id), "full_name": user.full_name, "email": user.email,
                 "company_id": str(user.company_id), "role": user.role},
        "metrics": {"email_count": email_count or 0, "reschedule_count": reschedule_count or 0},
        "google_connected": google_connected is not None,
    }