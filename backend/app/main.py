from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text

from app.api.router import api_router
from app.core.config import settings
from app.core.security import hash_password
from app.db.database import engine
from app.db.base import Base
from app.models.company import Company
from app.models.user import User
from app.models import company, user, agent, google_connection, email_message  # noqa: F401 - registers models
from app.services.mail_worker import inbox_worker


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Development bootstrap. Replace with Alembic migrations in production.
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(30) "
            "NOT NULL DEFAULT 'recruiter'"
        ))
        await connection.execute(text(
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS mailbox_email VARCHAR(255)"
        ))
        await connection.execute(text(
            "ALTER TABLE agents ADD COLUMN IF NOT EXISTS mailbox_connected BOOLEAN NOT NULL DEFAULT FALSE"
        ))
    from app.db.database import SessionFactory
    async with SessionFactory() as session:
        admin_email = settings.admin_email.lower().strip()
        admin = await session.scalar(select(User).where(User.email == admin_email))
        if not admin:
            company_record = Company(name="Recruiter Portal Administration")
            admin = User(company=company_record, full_name=settings.admin_name,
                         email=admin_email, password_hash=hash_password(settings.admin_password),
                         role="admin")
            session.add(admin)
            await session.commit()
        elif admin.role != "admin":
            admin.role = "admin"
            await session.commit()
    stop_event = asyncio.Event()
    worker = asyncio.create_task(inbox_worker(stop_event, settings.google_sync_interval_seconds))
    yield
    stop_event.set()
    await worker
    await engine.dispose()


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}
