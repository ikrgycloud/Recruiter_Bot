import asyncio
import logging

from sqlalchemy import select

from app.db.database import SessionFactory
from app.models.email_message import EmailMessage
from app.models.google_connection import GoogleConnection
from app.services.google_workspace import classify_message, credentials_from_connection, list_message_ids, read_message, run_sync

logger = logging.getLogger(__name__)


async def sync_connected_inboxes() -> None:
    async with SessionFactory() as session:
        connections = list(await session.scalars(select(GoogleConnection)))
        for connection in connections:
            try:
                credentials, refreshed = await run_sync(credentials_from_connection, connection)
                message_ids = await run_sync(list_message_ids, credentials, 25)
                for message_id in message_ids:
                    exists = await session.scalar(select(EmailMessage).where(
                        EmailMessage.user_id == connection.user_id,
                        EmailMessage.provider_message_id == message_id,
                    ))
                    if exists:
                        continue
                    message = await run_sync(read_message, credentials, message_id)
                    session.add(EmailMessage(
                        user_id=connection.user_id,
                        **message,
                        classification=classify_message(message["subject"] or "", message["body_preview"] or ""),
                    ))
                await session.commit()
            except Exception:
                await session.rollback()
                logger.exception("Google inbox sync failed for user %s", connection.user_id)


async def inbox_worker(stop_event: asyncio.Event, interval_seconds: int) -> None:
    while not stop_event.is_set():
        await sync_connected_inboxes()
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue
