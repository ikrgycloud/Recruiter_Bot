import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.db.database import SessionFactory
from app.models.email_message import EmailMessage
from app.models.google_connection import GoogleConnection
from app.models.outlook_connection import OutlookConnection
from app.models.mailbox_sync import MailboxSync
from app.services.google_workspace import classify_message, credentials_from_connection, list_message_ids, read_message, run_sync
from app.services.outlook_workspace import credentials_from_connection as outlook_credentials_from_connection
from app.services.outlook_workspace import list_message_ids as outlook_list_message_ids, read_message as outlook_read_message

logger = logging.getLogger(__name__)
_invalid_google_users: set[str] = set()


def clear_invalid_google_user(user_id) -> None:
    """Resume inbox polling after the user completes Google OAuth again."""
    _invalid_google_users.discard(str(user_id))


async def sync_connected_inboxes() -> None:
    async with SessionFactory() as session:
        # Sync Outlook first so a stale Google token cannot prevent a healthy
        # Microsoft mailbox from being imported.
        outlook_connections = (await session.scalars(select(OutlookConnection))).all()
        for connection in outlook_connections:
            user_id = connection.user_id
            try:
                token, refreshed = await run_sync(outlook_credentials_from_connection, connection)
                if refreshed:
                    await session.commit()
                known_ids = set((await session.scalars(select(EmailMessage.provider_message_id).where(
                    EmailMessage.user_id == user_id, EmailMessage.provider == "outlook"
                ))).all())
                for message_id in await run_sync(outlook_list_message_ids, token, None):
                    if message_id in known_ids:
                        continue
                    message = await run_sync(outlook_read_message, token, message_id)
                    session.add(EmailMessage(user_id=user_id, provider="outlook", **message,
                                             classification=classify_message(message["subject"], message["body_preview"])))
                await session.commit()
            except ValueError as exc:
                await session.rollback()
                logger.warning("Outlook inbox sync paused for user %s: %s", user_id, exc)
            except Exception:
                await session.rollback()
                logger.exception("Outlook inbox sync failed for user %s", user_id)
        google_user_ids = (await session.scalars(select(GoogleConnection.user_id))).all()
        for user_id in google_user_ids:
            connection = await session.get(GoogleConnection, user_id)
            if str(user_id) in _invalid_google_users:
                continue
            try:
                credentials, _ = await run_sync(credentials_from_connection, connection)
                sync_state = await session.get(MailboxSync, user_id)
                if sync_state is None:
                    sync_state = MailboxSync(user_id=user_id, initial_sync_complete=False)
                    session.add(sync_state)
                    await session.flush()
                known_ids = set((await session.scalars(
                    select(EmailMessage.provider_message_id).where(EmailMessage.user_id == user_id)
                )).all())
                stop_at_known = known_ids if sync_state.initial_sync_complete else None
                message_ids = await run_sync(list_message_ids, credentials, None, stop_at_known)
                for message_id in message_ids:
                    exists = await session.scalar(select(EmailMessage).where(
                        EmailMessage.user_id == user_id,
                        EmailMessage.provider_message_id == message_id,
                    ))
                    if exists:
                        continue
                    message = await run_sync(read_message, credentials, message_id)
                    record = EmailMessage(
                        user_id=user_id,
                        provider="google",
                        **message,
                        classification=classify_message(message["subject"] or "", message["body_preview"] or ""),
                    )
                    session.add(record)
                    await session.flush()
                sync_state.initial_sync_complete = True
                sync_state.last_synced_at = datetime.now(timezone.utc)
                await session.commit()
                _invalid_google_users.discard(str(user_id))
            except ValueError as exc:
                await session.rollback()
                if "reconnect Google" not in str(exc):
                    logger.exception("Google inbox sync failed for user %s", user_id)
                    continue
                if str(user_id) not in _invalid_google_users:
                    logger.warning(
                        "Google inbox sync paused for user %s; reconnect Google to resume (%s)",
                        user_id,
                        exc,
                    )
                    _invalid_google_users.add(str(user_id))
            except Exception:
                await session.rollback()
                logger.exception("Google inbox sync failed for user %s", user_id)


async def inbox_worker(stop_event: asyncio.Event, interval_seconds: int) -> None:
    interval_seconds = max(30, interval_seconds)
    while not stop_event.is_set():
        try:
            await sync_connected_inboxes()
        except Exception:
            logger.exception("Mailbox sync cycle failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue




