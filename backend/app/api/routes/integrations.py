import json
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
import httpx
from google_auth_oauthlib.flow import Flow
from jose import JWTError, jwt
from sqlalchemy import select

from app.api.dependencies import DbSession, get_current_user
from app.core.config import settings
from app.core.token_store import encrypt_token
from app.db.database import SessionFactory
from app.models.google_connection import GoogleConnection
from app.models.user import User
from app.models.email_message import EmailMessage
from app.models.outlook_connection import OutlookConnection
from app.services.google_workspace import (classify_message, credentials_from_connection, find_events,
                                           freebusy, list_message_ids, move_event, read_message, run_sync,
                                           send_reply, profile_email)

router = APIRouter()
GOOGLE_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
)


def configured_flow(state: str | None = None) -> Flow:
    placeholders = {"your_client_id_here", "your_client_secret_here"}
    if (not settings.google_client_id or not settings.google_client_secret or
            settings.google_client_id in placeholders or settings.google_client_secret in placeholders):
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }
    return Flow.from_client_config(client_config, scopes=list(GOOGLE_SCOPES), state=state,
                                   redirect_uri=settings.google_redirect_uri)


def create_state(user_id: uuid.UUID, provider: str = "google") -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=10)
    claims = {"sub": str(user_id), "purpose": "oauth", "provider": provider, "exp": expires}
    return jwt.encode(claims,
                      settings.jwt_secret, algorithm=settings.jwt_algorithm)


@router.get("/google/authorize")
async def google_authorize(user: User = Depends(get_current_user)) -> dict[str, str]:
    state = create_state(user.id)
    flow = configured_flow(state)
    authorization_url, _ = flow.authorization_url(access_type="offline", prompt="consent",
                                                    include_granted_scopes="true")
    return {"authorization_url": authorization_url}


@router.get("/google/callback")
async def google_callback(request: Request) -> RedirectResponse:
    error = request.query_params.get("error")
    if error:
        target = f"{settings.google_frontend_url}/dashboard/integrations?google=error&reason={urllib.parse.quote(error)}"
        return RedirectResponse(target)
    state = request.query_params.get("state")
    code = request.query_params.get("code")
    if not state or not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Google OAuth callback data")
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("purpose") != "oauth" or payload.get("provider") != "google":
            raise JWTError
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired Google OAuth state")

    flow = configured_flow(state)
    flow.fetch_token(code=code)
    credentials = flow.credentials
    mailbox_email = await run_sync(profile_email, credentials)
    async with SessionFactory() as session:
        user = await session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        connection = await session.scalar(select(GoogleConnection).where(GoogleConnection.user_id == user_id))
        if not connection:
            connection = GoogleConnection(user_id=user_id, token_json=encrypt_token(credentials.to_json()))
            session.add(connection)
        else:
            connection.token_json = encrypt_token(credentials.to_json())
        connection.email = mailbox_email
        await session.commit()
    return RedirectResponse(f"{settings.google_frontend_url}/dashboard/integrations?google=connected")


@router.get("/outlook/authorize")
async def outlook_authorize(user: User = Depends(get_current_user)) -> dict[str, str]:
    if not settings.microsoft_client_id or not settings.microsoft_client_secret:
        raise HTTPException(status_code=503, detail="Microsoft OAuth is not configured")
    state = create_state(user.id, "outlook")
    params = urllib.parse.urlencode({
        "client_id": settings.microsoft_client_id,
        "response_type": "code",
        "redirect_uri": settings.microsoft_redirect_uri,
        "response_mode": "query",
        "scope": "openid profile email offline_access Mail.Read Mail.Send Calendars.ReadWrite",
        "state": state,
    })
    return {"authorization_url": f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize?{params}"}


@router.get("/outlook/callback")
async def outlook_callback(request: Request) -> RedirectResponse:
    error = request.query_params.get("error")
    if error:
        reason = request.query_params.get("error_description", error)
        target = f"{settings.google_frontend_url}/dashboard/integrations?outlook=error&reason={urllib.parse.quote(reason)}"
        return RedirectResponse(target)
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing Microsoft OAuth callback data")
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("purpose") != "oauth" or payload.get("provider") != "outlook":
            raise JWTError
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid or expired Microsoft OAuth state")
    async with httpx.AsyncClient(timeout=20) as client:
        token_response = await client.post("https://login.microsoftonline.com/common/oauth2/v2.0/token", data={
            "client_id": settings.microsoft_client_id,
            "client_secret": settings.microsoft_client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.microsoft_redirect_uri,
        })
        if token_response.is_error:
            try:
                token_error = token_response.json()
            except ValueError:
                token_error = {}
            detail = token_error.get("error_description") or token_error.get("error") or "Microsoft OAuth token exchange failed"
            raise HTTPException(status_code=502, detail=detail)
        token = token_response.json()
        profile_response = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {token['access_token']}"},
        )
        profile = profile_response.json() if not profile_response.is_error else {}
    async with SessionFactory() as session:
        connection = await session.scalar(select(OutlookConnection).where(OutlookConnection.user_id == user_id))
        email = profile.get("mail") or profile.get("userPrincipalName")
        if not connection:
            session.add(OutlookConnection(user_id=user_id, email=email, token_json=encrypt_token(json.dumps(token))))
        else:
            connection.email = email
            connection.token_json = encrypt_token(json.dumps(token))
        await session.commit()
    return RedirectResponse(f"{settings.google_frontend_url}/dashboard/integrations?outlook=connected")


@router.get("/outlook/status")
async def outlook_status(session: DbSession, user: User = Depends(get_current_user)) -> dict[str, bool]:
    connected = await session.scalar(select(OutlookConnection.id).where(OutlookConnection.user_id == user.id))
    return {"connected": connected is not None}


@router.delete("/outlook")
async def disconnect_outlook(session: DbSession, user: User = Depends(get_current_user)) -> dict[str, bool]:
    connection = await session.scalar(select(OutlookConnection).where(OutlookConnection.user_id == user.id))
    if connection:
        await session.delete(connection)
        await session.commit()
    return {"connected": False}


@router.get("/google/status")
async def google_status(session: DbSession, user: User = Depends(get_current_user)) -> dict[str, bool]:
    connected = await session.scalar(select(GoogleConnection.id).where(GoogleConnection.user_id == user.id))
    return {"connected": connected is not None}


@router.delete("/google")
async def disconnect_google(session: DbSession, user: User = Depends(get_current_user)) -> dict[str, bool]:
    connection = await session.scalar(select(GoogleConnection).where(GoogleConnection.user_id == user.id))
    if connection:
        await session.delete(connection)
        await session.commit()
    return {"connected": False}


async def _connection(session, user: User) -> GoogleConnection:
    connection = await session.scalar(select(GoogleConnection).where(GoogleConnection.user_id == user.id))
    if not connection:
        raise HTTPException(status_code=409, detail="Connect Google before using Gmail or Calendar")
    return connection


@router.post("/google/gmail/sync")
async def sync_gmail(max_results: int = 25, session: DbSession = None,
                     user: User = Depends(get_current_user)) -> dict[str, Any]:
    connection = await _connection(session, user)
    credentials, refreshed = await run_sync(credentials_from_connection, connection)
    if refreshed:
        await session.commit()
    message_ids = await run_sync(list_message_ids, credentials, min(max_results, 100))
    saved: list[dict[str, Any]] = []
    for message_id in message_ids:
        exists = await session.scalar(select(EmailMessage).where(
            EmailMessage.user_id == user.id, EmailMessage.provider_message_id == message_id))
        if exists:
            saved.append({"id": str(exists.id), "classification": exists.classification})
            continue
        message = await run_sync(read_message, credentials, message_id)
        record = EmailMessage(user_id=user.id, **message,
                              classification=classify_message(message["subject"] or "", message["body_preview"] or ""))
        session.add(record)
        await session.flush()
        saved.append({"id": str(record.id), "provider_message_id": message_id, "classification": record.classification})
    await session.commit()
    return {"synced": len(saved), "messages": saved}


@router.get("/google/gmail/messages")
async def gmail_messages(limit: int = 50, session: DbSession = None,
                         user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    records = await session.scalars(select(EmailMessage).where(EmailMessage.user_id == user.id)
                                    .order_by(EmailMessage.received_at.desc()).limit(min(limit, 200)))
    return [{"id": str(item.id), "provider_message_id": item.provider_message_id, "sender": item.sender,
             "subject": item.subject, "body_preview": item.body_preview, "received_at": item.received_at,
             "classification": item.classification, "processed": item.processed} for item in records]


@router.post("/google/gmail/reply")
async def gmail_reply(payload: dict[str, str], session: DbSession = None,
                      user: User = Depends(get_current_user)) -> dict[str, str]:
    connection = await _connection(session, user)
    credentials, refreshed = await run_sync(credentials_from_connection, connection)
    if refreshed:
        await session.commit()
    required = {"to", "subject", "body"}
    if not required.issubset(payload):
        raise HTTPException(status_code=422, detail="to, subject, and body are required")
    sent = await run_sync(send_reply, credentials, payload["to"], payload["subject"], payload["body"], payload.get("thread_id"))
    return {"provider_message_id": sent.get("id", "")}


@router.get("/google/calendar/availability")
async def calendar_availability(start: datetime, end: datetime, session: DbSession = None,
                               user: User = Depends(get_current_user)) -> dict[str, Any]:
    if end <= start:
        raise HTTPException(status_code=422, detail="end must be after start")
    connection = await _connection(session, user)
    credentials, refreshed = await run_sync(credentials_from_connection, connection)
    if refreshed:
        await session.commit()
    result = await run_sync(freebusy, credentials, start, end)
    busy = result.get("calendars", {}).get("primary", {}).get("busy", [])
    return {"available": not busy, "busy": busy, "start": start, "end": end}


@router.get("/google/calendar/events")
async def calendar_events(start: datetime, end: datetime, query: str | None = None,
                          session: DbSession = None, user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    connection = await _connection(session, user)
    credentials, refreshed = await run_sync(credentials_from_connection, connection)
    if refreshed:
        await session.commit()
    return await run_sync(find_events, credentials, start, end, query)


@router.post("/google/calendar/reschedule")
async def calendar_reschedule(payload: dict[str, str], session: DbSession = None,
                              user: User = Depends(get_current_user)) -> dict[str, Any]:
    required = {"event_id", "start", "end"}
    if not required.issubset(payload):
        raise HTTPException(status_code=422, detail="event_id, start, and end are required")
    start = datetime.fromisoformat(payload["start"])
    end = datetime.fromisoformat(payload["end"])
    connection = await _connection(session, user)
    credentials, refreshed = await run_sync(credentials_from_connection, connection)
    if refreshed:
        await session.commit()
    availability = await run_sync(freebusy, credentials, start, end)
    busy = availability.get("calendars", {}).get("primary", {}).get("busy", [])
    if busy:
        raise HTTPException(status_code=409, detail={"message": "Requested time is busy", "busy": busy})
    event = await run_sync(move_event, credentials, payload["event_id"], start, end, payload.get("timezone", "UTC"))
    if payload.get("email_message_id"):
        message = await session.get(EmailMessage, uuid.UUID(payload["email_message_id"]))
        if message and message.sender:
            await run_sync(send_reply, credentials, message.sender, message.subject or "Interview update",
                           f"Your interview has been rescheduled to {start.isoformat()}.", message.thread_id)
            message.processed = True
            await session.commit()
    return {"event_id": event.get("id"), "status": "rescheduled", "start": start, "end": end}


@router.post("/google/automation/process/{message_id}")
async def process_reschedule_request(message_id: uuid.UUID, payload: dict[str, Any], session: DbSession = None,
                                     user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Classify an email and optionally move its matching Calendar event.

    Defaults to a dry run. Set execute=true only after reviewing the proposed result.
    """
    message = await session.scalar(select(EmailMessage).where(
        EmailMessage.id == message_id, EmailMessage.user_id == user.id))
    if not message:
        raise HTTPException(status_code=404, detail="Email message not found")
    message.classification = classify_message(message.subject or "", message.body_preview or "")
    if message.classification != "reschedule_request":
        await session.commit()
        return {"status": "ignored", "classification": message.classification}
    required = {"proposed_start", "proposed_end"}
    if not required.issubset(payload):
        raise HTTPException(status_code=422, detail="proposed_start and proposed_end are required")
    proposed_start = datetime.fromisoformat(str(payload["proposed_start"]))
    proposed_end = datetime.fromisoformat(str(payload["proposed_end"]))
    connection = await _connection(session, user)
    credentials, refreshed = await run_sync(credentials_from_connection, connection)
    if refreshed:
        await session.commit()
    events = await run_sync(find_events, credentials, proposed_start - timedelta(days=30),
                            proposed_end + timedelta(days=30), message.sender or None)
    event_id = str(payload.get("event_id") or (events[0].get("id") if events else ""))
    availability = await run_sync(freebusy, credentials, proposed_start, proposed_end)
    busy = availability.get("calendars", {}).get("primary", {}).get("busy", [])
    result: dict[str, Any] = {
        "status": "needs_approval", "classification": message.classification,
        "event_id": event_id or None, "available": not busy, "busy": busy,
        "proposed_start": proposed_start, "proposed_end": proposed_end,
    }
    execute = bool(payload.get("execute", False))
    if not execute and settings.automation_auto_reschedule:
        execute = True
    if execute:
        if not event_id:
            raise HTTPException(status_code=404, detail="No matching Calendar event found")
        if busy:
            raise HTTPException(status_code=409, detail={"message": "Requested time is busy", "busy": busy})
        event = await run_sync(move_event, credentials, event_id, proposed_start, proposed_end,
                               str(payload.get("timezone", "UTC")))
        if message.sender:
            await run_sync(send_reply, credentials, message.sender, message.subject or "Interview update",
                           f"Your interview has been rescheduled to {proposed_start.isoformat()}.", message.thread_id)
        message.processed = True
        result.update({"status": "rescheduled", "event_id": event.get("id")})
    await session.commit()
    return result