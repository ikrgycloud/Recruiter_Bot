"""Small Microsoft Graph adapter used by the Outlook mailbox workflow."""
import json
import re
from html import unescape
from datetime import datetime, timezone
from email.utils import parseaddr
from typing import Any

import httpx

from app.core.config import settings
from app.core.token_store import decrypt_token, encrypt_token

GRAPH = "https://graph.microsoft.com/v1.0"


def _token(connection) -> dict[str, Any]:
    return json.loads(decrypt_token(connection.token_json))


def credentials_from_connection(connection) -> tuple[dict[str, Any], bool]:
    token = _token(connection)
    expires_at = token.get("expires_at")
    if expires_at and float(expires_at) > datetime.now(timezone.utc).timestamp() + 60:
        return token, False
    refresh = token.get("refresh_token")
    if not refresh:
        raise ValueError("Outlook access token expired. Please reconnect Outlook.")
    response = httpx.post("https://login.microsoftonline.com/common/oauth2/v2.0/token", data={
        "client_id": settings.microsoft_client_id, "client_secret": settings.microsoft_client_secret,
        "grant_type": "refresh_token", "refresh_token": refresh,
        "scope": "openid profile email offline_access Mail.Read Mail.Send Calendars.ReadWrite",
    }, timeout=20)
    if response.is_error:
        raise ValueError("Outlook access token expired or revoked. Please reconnect Outlook.")
    refreshed = response.json()
    refreshed["refresh_token"] = refreshed.get("refresh_token", refresh)
    refreshed["expires_at"] = datetime.now(timezone.utc).timestamp() + int(refreshed.get("expires_in", 3600))
    connection.token_json = encrypt_token(json.dumps(refreshed))
    return refreshed, True


def _request(token: dict[str, Any], method: str, path: str, **kwargs):
    response = httpx.request(method, GRAPH + path, headers={"Authorization": f"Bearer {token['access_token']}"}, timeout=25, **kwargs)
    if response.is_error:
        raise ValueError(f"Microsoft Graph request failed ({response.status_code})")
    return response


def list_message_ids(token: dict[str, Any], max_results: int = 50) -> list[str]:
    # /me/messages works for both Outlook.com and Microsoft 365 mailboxes;
    # localized folder names can make /mailFolders/inbox return an empty page.
    response = _request(token, "GET", "/me/messages", params={
        "$top": min(max_results or 50, 100), "$select": "id", "$orderby": "receivedDateTime desc",
    })
    return [item["id"] for item in response.json().get("value", [])]


def read_message(token: dict[str, Any], message_id: str) -> dict[str, Any]:
    response = _request(token, "GET", f"/me/messages/{message_id}", params={
        "$select": "id,conversationId,subject,receivedDateTime,from,body,bodyPreview,internetMessageId",
    })
    item = response.json()
    sender = item.get("from", {}).get("emailAddress", {})
    body = item.get("body", {}).get("content") or item.get("bodyPreview") or ""
    if item.get("body", {}).get("contentType") == "html":
        body = unescape(re.sub(r"<[^>]+>", " ", body))
    return {
        "provider_message_id": item.get("id"), "thread_id": item.get("conversationId"),
        "sender": f"{sender.get('name', '')} <{sender.get('address', '')}>".strip(),
        "subject": item.get("subject") or "", "body_preview": body,
        "received_at": datetime.fromisoformat(item["receivedDateTime"].replace("Z", "+00:00")),
    }


def send_message(token: dict[str, Any], to: str, subject: str, body: str) -> dict[str, Any]:
    address = parseaddr(to)[1] or to
    payload = {"message": {"subject": subject if subject.lower().startswith("re:") else f"Re: {subject}",
                           "body": {"contentType": "Text", "content": body},
                           "toRecipients": [{"emailAddress": {"address": address}}]}, "saveToSentItems": True}
    response = _request(token, "POST", "/me/sendMail", json=payload)
    return response.json() if response.content else {}


def find_events(token: dict[str, Any], start: datetime, end: datetime) -> list[dict[str, Any]]:
    response = _request(token, "GET", "/me/calendarView", params={
        "startDateTime": start.isoformat(), "endDateTime": end.isoformat(), "$top": 1000,
        "$orderby": "start/dateTime",
    })
    return response.json().get("value", [])


def move_event(token: dict[str, Any], event_id: str, start: datetime, end: datetime, timezone_name: str = "UTC") -> dict[str, Any]:
    return _request(token, "PATCH", f"/me/events/{event_id}", json={
        "start": {"dateTime": start.isoformat(), "timeZone": timezone_name},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone_name},
    }).json()
