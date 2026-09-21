import json
import logging
import urllib.parse
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
import httpx
from google_auth_oauthlib.flow import Flow
from jose import JWTError, jwt
from sqlalchemy import func, select

from app.api.dependencies import DbSession, get_current_user
from app.core.config import settings
from app.core.token_store import encrypt_token
from app.db.database import SessionFactory
from app.models.google_connection import GoogleConnection
from app.models.user import User
from app.models.email_message import EmailMessage
from app.models.automation_preference import AutomationPreference
from app.models.outlook_connection import OutlookConnection
from app.services.google_workspace import (classify_message, credentials_from_connection, find_events,
                                           freebusy, list_message_ids, move_event,
                                           primary_calendar_timezone, read_message, run_sync,
                                           send_reply, profile_email)
from app.services.rescheduling import (build_reschedule_plan, execute_reschedule_plan,
                                       slot_is_available, slot_matches_work_schedule)
from app.services.mail_worker import clear_invalid_google_user

router = APIRouter()
logger = logging.getLogger(__name__)
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
    clear_invalid_google_user(user_id)
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
async def google_status(session: DbSession, user: User = Depends(get_current_user)) -> dict[str, Any]:
    connection = await session.scalar(select(GoogleConnection).where(GoogleConnection.user_id == user.id))
    if not connection:
        return {"connected": False, "reconnect_required": False}
    try:
        _, refreshed = await run_sync(credentials_from_connection, connection)
        if refreshed:
            await session.commit()
        return {"connected": True, "reconnect_required": False}
    except ValueError as exc:
        return {"connected": False, "reconnect_required": True, "message": str(exc)}


@router.delete("/google")
async def disconnect_google(session: DbSession, user: User = Depends(get_current_user)) -> dict[str, bool]:
    connection = await session.scalar(select(GoogleConnection).where(GoogleConnection.user_id == user.id))
    if connection:
        await session.delete(connection)
        await session.commit()
    return {"connected": False}


@router.get("/google/gmail/status")
async def gmail_status(session: DbSession, user: User = Depends(get_current_user)) -> dict[str, Any]:
    connection = await session.scalar(select(GoogleConnection).where(GoogleConnection.user_id == user.id))
    if not connection:
        return {"connected": False, "reconnect_required": False, "email": None, "message_count": 0}
    try:
        _, refreshed = await run_sync(credentials_from_connection, connection)
        if refreshed:
            await session.commit()
    except ValueError as exc:
        return {"connected": False, "reconnect_required": True, "message": str(exc),
                "email": connection.email, "message_count": 0}
    message_count = await session.scalar(select(func.count(EmailMessage.id)).where(EmailMessage.user_id == user.id))
    return {
        "connected": True,
        "reconnect_required": False,
        "email": connection.email,
        "message_count": message_count or 0,
    }


async def _connection(session, user: User) -> GoogleConnection:
    connection = await session.scalar(select(GoogleConnection).where(GoogleConnection.user_id == user.id))
    if not connection:
        raise HTTPException(status_code=409, detail="Connect Google before using Gmail or Calendar")
    return connection


async def _google_credentials(session, user: User) -> tuple[Any, bool]:
    connection = await _connection(session, user)
    try:
        credentials, refreshed = await run_sync(credentials_from_connection, connection)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    if refreshed:
        await session.commit()
    return credentials, refreshed


async def _auto_suggestions_enabled(session, user: User) -> bool:
    preference = await session.get(AutomationPreference, user.id)
    return (preference.automatic_rescheduling_enabled if preference
            else settings.automation_auto_reschedule)


async def _work_schedule(session, user: User) -> tuple[list[int], time, time]:
    preference = await session.get(AutomationPreference, user.id)
    if preference:
        return preference.working_days, preference.shift_start, preference.shift_end
    return [0, 1, 2, 3, 4], time(9), time(17)


async def _build_user_reschedule_plan(session, user: User, message: EmailMessage, credentials) -> dict:
    if message.provider_message_id:
        try:
            full_message = await run_sync(read_message, credentials, message.provider_message_id)
        except Exception as exc:
            logger.exception("Unable to refresh full Gmail content for message %s", message.id)
            return {"status": "needs_review", "reason": "The complete email could not be read from Gmail. Retry syncing before approving."}
        message.sender = full_message["sender"]
        message.subject = full_message["subject"]
        message.body_preview = full_message["body_preview"]
        message.thread_id = full_message["thread_id"]
        message.received_at = full_message["received_at"]
        message.classification = classify_message(message.subject or "", message.body_preview or "")
        await session.commit()
        if message.classification != "reschedule_request":
            return {"status": "needs_review", "reason": "The latest email content does not contain a reschedule request."}
    working_days, shift_start, shift_end = await _work_schedule(session, user)
    return await build_reschedule_plan(
        message, credentials, working_days=working_days,
        shift_start=shift_start, shift_end=shift_end,
    )


@router.post("/google/gmail/sync")
async def sync_gmail(max_results: int = 25, session: DbSession = None,
                     user: User = Depends(get_current_user)) -> dict[str, Any]:
    credentials, _ = await _google_credentials(session, user)
    if max_results is None or max_results <= 0:
        max_results = 25
    message_ids = await run_sync(list_message_ids, credentials, max_results)
    saved: list[dict[str, Any]] = []
    new_count = 0
    existing_count = 0
    for message_id in message_ids:
        try:
            exists = await session.scalar(select(EmailMessage).where(
                EmailMessage.user_id == user.id, EmailMessage.provider_message_id == message_id))
            if exists:
                existing_count += 1
                # Refresh the complete Gmail payload too; older imports may
                # contain only a shallow MIME part or no body at all.
                refreshed_message = await run_sync(read_message, credentials, message_id)
                exists.sender = refreshed_message["sender"]
                exists.subject = refreshed_message["subject"]
                exists.body_preview = refreshed_message["body_preview"]
                exists.thread_id = refreshed_message["thread_id"]
                exists.received_at = refreshed_message["received_at"]
                latest_classification = classify_message(
                    exists.subject or "", exists.body_preview or ""
                )
                if exists.classification != latest_classification:
                    exists.classification = latest_classification
                saved.append({"id": str(exists.id), "classification": exists.classification})
                continue
            message = await run_sync(read_message, credentials, message_id)
            record = EmailMessage(user_id=user.id, **message,
                                  classification=classify_message(message["subject"] or "", message["body_preview"] or ""))
            session.add(record)
            await session.flush()
            new_count += 1
            saved.append({"id": str(record.id), "provider_message_id": message_id, "classification": record.classification})
        except HttpError as exc:
            if exc.resp is not None and exc.resp.status == 403:
                raise HTTPException(status_code=429, detail="Google Gmail API quota reached. Please wait a moment and retry the sync.") from exc
            raise HTTPException(status_code=502, detail="Google Gmail request failed") from exc
    await session.commit()
    return {"synced": len(saved), "new": new_count, "existing": existing_count,
            "messages": saved}


@router.get("/google/gmail/messages")
async def gmail_messages(page: int = 1, page_size: int = 25, session: DbSession = None,
                         user: User = Depends(get_current_user)) -> dict[str, Any]:
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 25
    total = await session.scalar(select(func.count(EmailMessage.id)).where(EmailMessage.user_id == user.id))
    offset = (page - 1) * page_size
    records = await session.scalars(select(EmailMessage).where(EmailMessage.user_id == user.id)
                                    .order_by(EmailMessage.received_at.desc()).offset(offset).limit(page_size))
    records = list(records)
    # Existing database rows may have been classified with older rules. Update
    # their labels when listing so they appear correctly without reimporting.
    changed = False
    for item in records:
        classification = classify_message(item.subject or "", item.body_preview or "")
        if item.classification != classification:
            item.classification = classification
            changed = True
    if changed:
        await session.commit()
    items = [{"id": str(item.id), "provider_message_id": item.provider_message_id, "sender": item.sender,
             "subject": item.subject, "body_preview": item.body_preview, "received_at": item.received_at,
             "classification": item.classification, "processed": item.processed} for item in records]
    pages = max(1, (total + page_size - 1) // page_size) if total else 1
    return {"page": page, "page_size": page_size, "total": total or 0, "pages": pages, "items": items}


@router.get("/google/gmail/messages/{message_id}/body")
async def gmail_message_body(message_id: uuid.UUID, session: DbSession = None,
                             user: User = Depends(get_current_user)) -> dict[str, Any]:
    record = await session.scalar(select(EmailMessage).where(
        EmailMessage.id == message_id, EmailMessage.user_id == user.id
    ))
    if not record:
        raise HTTPException(status_code=404, detail="Email message not found")
    credentials, _ = await _google_credentials(session, user)
    try:
        refreshed = await run_sync(read_message, credentials, record.provider_message_id)
    except HttpError as exc:
        raise HTTPException(status_code=502, detail="Unable to fetch the complete email from Gmail") from exc
    record.sender = refreshed["sender"]
    record.subject = refreshed["subject"]
    record.body_preview = refreshed["body_preview"]
    record.thread_id = refreshed["thread_id"]
    record.received_at = refreshed["received_at"]
    record.classification = classify_message(record.subject or "", record.body_preview or "")
    await session.commit()
    return {"body": record.body_preview or "", "classification": record.classification}


@router.post("/google/gmail/reply")
async def gmail_reply(payload: dict[str, str], session: DbSession = None,
                      user: User = Depends(get_current_user)) -> dict[str, str]:
    credentials, _ = await _google_credentials(session, user)
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
    credentials, _ = await _google_credentials(session, user)
    result = await run_sync(freebusy, credentials, start, end)
    busy = result.get("calendars", {}).get("primary", {}).get("busy", [])
    return {"available": not busy, "busy": busy, "start": start, "end": end}


@router.get("/google/calendar/events")
async def calendar_events(start: datetime, end: datetime, query: str | None = None,
                          session: DbSession = None, user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    credentials, _ = await _google_credentials(session, user)
    return await run_sync(find_events, credentials, start, end, query)


@router.get("/google/calendar/week")
async def calendar_week(offset: int = 0, display_timezone: str | None = None, session: DbSession = None,
                        user: User = Depends(get_current_user)) -> dict[str, Any]:
    if offset < -52 or offset > 52:
        raise HTTPException(status_code=422, detail="Week offset must be between -52 and 52")
    credentials, _ = await _google_credentials(session, user)
    timezone_name = (display_timezone if display_timezone in {"UTC", "Asia/Kolkata"}
                     else await run_sync(primary_calendar_timezone, credentials))
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        zone = ZoneInfo("UTC")
        timezone_name = "UTC"
    today = datetime.now(zone).date()
    monday = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
    start = datetime.combine(monday, time.min, tzinfo=zone)
    end = start + timedelta(days=7)
    events = await run_sync(find_events, credentials, start, end)
    return {
        "timezone": timezone_name,
        "week_start": monday.isoformat(),
        "week_end": (monday + timedelta(days=6)).isoformat(),
        "events": events,
    }


@router.post("/google/calendar/reschedule")
async def calendar_reschedule(payload: dict[str, str], session: DbSession = None,
                              user: User = Depends(get_current_user)) -> dict[str, Any]:
    required = {"event_id", "start", "end"}
    if not required.issubset(payload):
        raise HTTPException(status_code=422, detail="event_id, start, and end are required")
    start = datetime.fromisoformat(payload["start"])
    end = datetime.fromisoformat(payload["end"])
    credentials, _ = await _google_credentials(session, user)
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


@router.get("/google/automation/pending")
async def pending_reschedule_requests(session: DbSession = None,
                                      user: User = Depends(get_current_user)) -> list[dict[str, Any]]:
    records = await session.scalars(select(EmailMessage).where(
        EmailMessage.user_id == user.id,
        EmailMessage.classification == "reschedule_request",
        EmailMessage.processed.is_(False),
    ).order_by(EmailMessage.received_at.desc()))
    pending: list[dict[str, Any]] = []
    credentials = None
    suggest_automatically = await _auto_suggestions_enabled(session, user)
    rows = records.all()
    if rows:
        try:
            credentials, _ = await _google_credentials(session, user)
        except HTTPException:
            credentials = None
    for message in rows:
        plan = await _build_user_reschedule_plan(session, user, message, credentials) if credentials else {
            "status": "needs_review", "reason": "Connect Google before planning a calendar change."}
        if message.classification != "reschedule_request":
            continue
        if not suggest_automatically and plan.get("status") == "ready":
            plan = {**plan, "status": "needs_review",
                    "reason": "Automatic suggestions are off. Choose a date and time for recruiter review."}
            plan.pop("start", None)
            plan.pop("end", None)
        pending.append({
            "id": str(message.id),
            "sender": message.sender,
            "subject": message.subject,
            "body_preview": message.body_preview,
            "received_at": message.received_at.isoformat() if message.received_at else None,
            "classification": message.classification,
            **plan,
        })
    return pending


@router.post("/google/automation/review/{message_id}/approve")
async def approve_reschedule_request(message_id: uuid.UUID, payload: dict[str, Any], session: DbSession = None,
                                    user: User = Depends(get_current_user)) -> dict[str, Any]:
    message = await session.scalar(select(EmailMessage).where(
        EmailMessage.id == message_id, EmailMessage.user_id == user.id))
    if not message:
        raise HTTPException(status_code=404, detail="Email message not found")
    if message.processed:
        raise HTTPException(status_code=409, detail="This email has already been handled")
    credentials, _ = await _google_credentials(session, user)
    plan = await _build_user_reschedule_plan(session, user, message, credentials)
    if payload.get("start") and payload.get("end"):
        proposed_start = datetime.fromisoformat(str(payload["start"]))
        proposed_end = datetime.fromisoformat(str(payload["end"]))
        zone = ZoneInfo(str(plan.get("timezone", "UTC")))
        if proposed_start.tzinfo is None:
            proposed_start = proposed_start.replace(tzinfo=zone)
        if proposed_end.tzinfo is None:
            proposed_end = proposed_end.replace(tzinfo=zone)
        if proposed_end <= proposed_start:
            raise HTTPException(status_code=422, detail="end must be after start")
        if not plan.get("event_id"):
            raise HTTPException(status_code=409, detail=plan.get("reason", "Link this suggestion to its Google Calendar event before rescheduling."))
        if not await slot_is_available(credentials, plan["event_id"], proposed_start, proposed_end):
            raise HTTPException(status_code=409, detail="That calendar time is no longer available")
        plan["start"], plan["end"] = proposed_start.isoformat(), proposed_end.isoformat()
        plan["status"] = "ready"
    elif payload.get("date") and payload.get("time"):
        if not plan.get("event_id"):
            raise HTTPException(status_code=409, detail=plan.get("reason", "Link this suggestion to its Google Calendar event before rescheduling."))
        try:
            zone = ZoneInfo(str(plan.get("timezone", "UTC")))
            proposed_start = datetime.combine(date.fromisoformat(str(payload["date"])),
                                              time.fromisoformat(str(payload["time"])), tzinfo=zone)
            proposed_end = proposed_start + timedelta(seconds=int(plan["duration_seconds"]))
        except (ValueError, KeyError) as exc:
            raise HTTPException(status_code=422, detail="Provide a valid date and time") from exc
        if not await slot_is_available(credentials, plan["event_id"], proposed_start, proposed_end):
            raise HTTPException(status_code=409, detail="That calendar time is no longer available")
        plan["start"], plan["end"] = proposed_start.isoformat(), proposed_end.isoformat()
        plan["status"] = "ready"
    elif plan.get("status") != "ready":
        raise HTTPException(status_code=409, detail=plan.get("reason", "This request needs manual review."))
    working_days, shift_start, shift_end = await _work_schedule(session, user)
    if not slot_matches_work_schedule(
        datetime.fromisoformat(plan["start"]), datetime.fromisoformat(plan["end"]),
        str(plan.get("timezone", "UTC")), working_days, shift_start, shift_end,
    ):
        raise HTTPException(status_code=422, detail="Choose a time inside the configured working days and shift")
    return await execute_reschedule_plan(session, message, credentials, plan)


@router.post("/google/automation/review/{message_id}/decline")
async def decline_reschedule_request(message_id: uuid.UUID, session: DbSession = None,
                                    user: User = Depends(get_current_user)) -> dict[str, Any]:
    message = await session.scalar(select(EmailMessage).where(
        EmailMessage.id == message_id, EmailMessage.user_id == user.id))
    if not message:
        raise HTTPException(status_code=404, detail="Email message not found")
    if message.processed:
        raise HTTPException(status_code=409, detail="This email has already been handled")
    message.processed = True
    message.classification = "other"
    await session.commit()
    return {"status": "declined", "message_id": str(message.id)}


@router.get("/google/automation/settings")
async def automation_settings(session: DbSession, user: User = Depends(get_current_user)) -> dict[str, Any]:
    enabled = await _auto_suggestions_enabled(session, user)
    working_days, shift_start, shift_end = await _work_schedule(session, user)
    return {
        "automatic_rescheduling_enabled": enabled,
        "sync_interval_seconds": settings.google_sync_interval_seconds,
        "default_mode": "suggest_and_approve" if enabled else "recruiter_selects",
        "working_days": working_days,
        "shift_start": shift_start.strftime("%H:%M"),
        "shift_end": shift_end.strftime("%H:%M"),
    }


@router.put("/google/automation/settings")
async def update_automation_settings(payload: dict[str, Any], session: DbSession,
                                     user: User = Depends(get_current_user)) -> dict[str, Any]:
    preference = await session.get(AutomationPreference, user.id)
    if not preference:
        preference = AutomationPreference(
            user_id=user.id,
            automatic_rescheduling_enabled=settings.automation_auto_reschedule,
        )
        session.add(preference)
    if "automatic_rescheduling_enabled" in payload:
        enabled = payload["automatic_rescheduling_enabled"]
        if not isinstance(enabled, bool):
            raise HTTPException(status_code=422, detail="automatic_rescheduling_enabled must be true or false")
        preference.automatic_rescheduling_enabled = enabled
    if "working_days" in payload:
        days = payload["working_days"]
        if (not isinstance(days, list) or not days or
                any(not isinstance(day, int) or isinstance(day, bool) or day not in range(7) for day in days)):
            raise HTTPException(status_code=422, detail="working_days must contain one or more weekdays from 0 to 6")
        preference.working_days = sorted(set(days))
    for key in ("shift_start", "shift_end"):
        if key in payload:
            try:
                value = time.fromisoformat(str(payload[key]))
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=f"{key} must use HH:MM format") from exc
            if value.tzinfo is not None or value.second or value.microsecond:
                raise HTTPException(status_code=422, detail=f"{key} must use local HH:MM time")
            setattr(preference, key, value)
    if preference.shift_end <= preference.shift_start:
        raise HTTPException(status_code=422, detail="shift_end must be later than shift_start")
    await session.commit()
    return await automation_settings(session, user)


@router.post("/google/automation/process/{message_id}")
async def process_reschedule_request(message_id: uuid.UUID, payload: dict[str, Any], session: DbSession = None,
                                     user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Plan a reschedule; execution is gated by approval or the explicit automation setting."""
    message = await session.scalar(select(EmailMessage).where(
        EmailMessage.id == message_id, EmailMessage.user_id == user.id))
    if not message:
        raise HTTPException(status_code=404, detail="Email message not found")
    if message.processed:
        raise HTTPException(status_code=409, detail="This email has already been handled")
    credentials, _ = await _google_credentials(session, user)
    plan = await _build_user_reschedule_plan(session, user, message, credentials)
    if message.classification != "reschedule_request":
        await session.commit()
        return {"status": "ignored", "classification": message.classification}
    if payload.get("proposed_start") and payload.get("proposed_end"):
        proposed_start = datetime.fromisoformat(str(payload["proposed_start"]))
        proposed_end = datetime.fromisoformat(str(payload["proposed_end"]))
        zone = ZoneInfo(str(plan.get("timezone", "UTC")))
        if proposed_start.tzinfo is None:
            proposed_start = proposed_start.replace(tzinfo=zone)
        if proposed_end.tzinfo is None:
            proposed_end = proposed_end.replace(tzinfo=zone)
        if proposed_end <= proposed_start:
            raise HTTPException(status_code=422, detail="proposed_end must be after proposed_start")
        if not plan.get("event_id"):
            raise HTTPException(status_code=409, detail=plan.get("reason", "Link this suggestion to its Google Calendar event before rescheduling."))
        if not await slot_is_available(credentials, plan["event_id"], proposed_start, proposed_end):
            raise HTTPException(status_code=409, detail="That calendar time is unavailable")
        plan.update({"status": "ready", "start": proposed_start.isoformat(),
                     "end": proposed_end.isoformat()})
    if plan.get("status") != "ready":
        return plan
    working_days, shift_start, shift_end = await _work_schedule(session, user)
    if not slot_matches_work_schedule(
        datetime.fromisoformat(plan["start"]), datetime.fromisoformat(plan["end"]),
        str(plan.get("timezone", "UTC")), working_days, shift_start, shift_end,
    ):
        raise HTTPException(status_code=422, detail="Choose a time inside the configured working days and shift")
    if bool(payload.get("execute", False)):
        return await execute_reschedule_plan(session, message, credentials, plan)
    return {**plan, "status": "needs_approval"}
