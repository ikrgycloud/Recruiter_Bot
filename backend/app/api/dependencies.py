from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.database import get_session
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=True)
DbSession = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
                           session: DbSession) -> User:
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = await session.scalar(select(User).where(User.id == UUID(user_id), User.is_active.is_(True)))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
