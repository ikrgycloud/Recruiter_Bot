import base64
import asyncio
import json
from datetime import datetime, timezone
from email.mime.text import MIMEText
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.core.token_store import decrypt_token, encrypt_token
from app.models.google_connection import GoogleConnection

RESCHEDULE_TERMS = (
    "reschedule", "change the interview", "change the date", "change the time",
    "different time", "different date", "cannot attend", "another slot", "postpone",
    "move the interview", "availability",
)
MAX_BODY_PREVIEW_LENGTH = 1000


def credentials_from_connection(connection: GoogleConnection) -> tuple[Credentials, bool]:
    credentials = Credentials.from_authorized_user_info(json.loads(decrypt_token(connection.token_json)))
    refreshed = False
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        connection.token_json = encrypt_token(credentials.to_json())
        refreshed = True
    return credentials, refreshed


def classify_message(subject: str, body: str) -> str:
    text = f"{subject} {body}".lower()
    return "reschedule_request" if any(term in text for term in RESCHEDULE_TERMS) else "other"


def _header(headers: list[dict[str, str]], name: str) -> str:
    return next((item["value"] for item in headers if item["name"].lower() == name.lower()), "")


def read_message(credentials: Credentials, message_id: str) -> dict[str, Any]:
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    payload = message.get("payload", {})
    body = payload.get("body", {}).get("data", "")
    if not body:
        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain":
                body = part.get("body", {}).get("data", "")
                break
    decoded = base64.urlsafe_b64decode(body + "===").decode("utf-8", errors="replace") if body else ""
    headers = payload.get("headers", [])
    return {
        "provider_message_id": message["id"], "thread_id": message.get("threadId"),
        "sender": _header(headers, "From"), "subject": _header(headers, "Subject"),
        "body_preview": decoded[:MAX_BODY_PREVIEW_LENGTH],
        "received_at": datetime.fromtimestamp(int(message.get("internalDate", "0")) / 1000, timezone.utc),
    }


def list_message_ids(credentials: Credentials, max_results: int = 25) -> list[str]:
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    response = service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=max_results).execute()
    return [item["id"] for item in response.get("messages", [])]


def profile_email(credentials: Credentials) -> str:
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    return service.users().getProfile(userId="me").execute()["emailAddress"]


def send_reply(credentials: Credentials, to: str, subject: str, body: str, thread_id: str | None = None) -> dict[str, Any]:
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    payload: dict[str, Any] = {"raw": raw}
    if thread_id:
        payload["threadId"] = thread_id
    return service.users().messages().send(userId="me", body=payload).execute()


def freebusy(credentials: Credentials, start: datetime, end: datetime) -> dict[str, Any]:
    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    return service.freebusy().query(body={"timeMin": start.isoformat(), "timeMax": end.isoformat(), "items": [{"id": "primary"}]}).execute()


def find_events(credentials: Credentials, start: datetime, end: datetime, query: str | None = None) -> list[dict[str, Any]]:
    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    return service.events().list(calendarId="primary", timeMin=start.isoformat(), timeMax=end.isoformat(), q=query,
                                 singleEvents=True, orderBy="startTime").execute().get("items", [])


def move_event(credentials: Credentials, event_id: str, start: datetime, end: datetime, timezone_name: str = "UTC") -> dict[str, Any]:
    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    return service.events().patch(calendarId="primary", eventId=event_id, body={
        "start": {"dateTime": start.isoformat(), "timeZone": timezone_name},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone_name},
    }, sendUpdates="all").execute()


async def run_sync(function, *args):
    return await asyncio.to_thread(function, *args)
