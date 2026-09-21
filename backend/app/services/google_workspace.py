import base64
import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import unescape
from typing import Any

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.token_store import decrypt_token, encrypt_token
from app.models.google_connection import GoogleConnection

IGNORE_PATTERNS = (
    "google account", "myaccount.google.com", "check activity", "security activity",
    "access to some of your google account data", "someone else may be trying to access",
    "interview reschedule bot access to some of your google account data",
    "delivery status notification (failure)", "mail delivery subsystem",
    "your message wasn't delivered", "your message was not delivered",
)


def extract_reschedule_dates(text: str) -> list[datetime]:
    cleaned = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", text, flags=re.IGNORECASE)
    matches = re.findall(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{1,2}\s+[A-Za-z]+\s+\d{2,4}\b", cleaned)
    parsed: list[datetime] = []
    for match in matches:
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d.%m.%y",
                    "%d %B %Y", "%d %b %Y"):
            try:
                parsed.append(datetime.strptime(match.strip(), fmt))
                break
            except ValueError:
                continue
    unique: list[datetime] = []
    seen: set[str] = set()
    for value in parsed:
        key = value.date().isoformat()
        if key not in seen:
            seen.add(key)
            unique.append(value)
    return unique


def infer_reschedule_window(subject: str, body: str) -> tuple[datetime | None, datetime | None]:
    text = f"{subject} {body}".lower()
    dates = extract_reschedule_dates(text)
    if not dates:
        return None, None
    proposed_start = dates[-1]
    proposed_end = proposed_start + timedelta(hours=1)
    return proposed_start, proposed_end


def credentials_from_connection(connection: GoogleConnection | str) -> tuple[Credentials, bool]:
    token_json = connection.token_json if hasattr(connection, "token_json") else connection
    try:
        credentials = Credentials.from_authorized_user_info(json.loads(decrypt_token(token_json)))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Google connection data is invalid. Please reconnect Google.") from exc

    refreshed = False
    if credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
            if hasattr(connection, "token_json"):
                connection.token_json = encrypt_token(credentials.to_json())
            refreshed = True
        except RefreshError as exc:
            raise ValueError("Google access token expired or revoked. Please reconnect Google.") from exc
    return credentials, refreshed


def classify_message(subject: str, body: str) -> str:
    subject_text = re.sub(r"\s+", " ", (subject or "").lower()).strip()
    body_text = re.sub(r"\s+", " ", latest_message_text(body).lower()).strip()
    text = f"{subject_text} {body_text}"
    if any(pattern in text for pattern in IGNORE_PATTERNS):
        return "other"
    # Match the intent in either word order ("change interview date" and
    # "interview date changing") and allow ordinary words between the terms.
    has_action = bool(re.search(
        r"\b(reschedul\w*|chang\w*|mov\w*|postpon\w*|shift\w*)\b", text
    ))
    has_meeting_context = bool(re.search(
        r"\b(interview\w*|meeting\w*|appointment\w*|slot\w*|call\w*|session\w*|schedule\w*)\b",
        text,
    ))
    if has_action and has_meeting_context:
        return "reschedule_request"
    # "I can't attend" is a reschedule request when an interview/meeting is
    # mentioned, even when the sender doesn't use the word "reschedule".
    if has_meeting_context and re.search(
        r"\b(can(?:not|'t)|unable to|won't be able to)\b.{0,50}\b(attend|make it|join)\b",
        text,
    ):
        return "reschedule_request"
    return "other"


def latest_message_text(body: str) -> str:
    """Remove quoted replies so old dates and times do not affect planning."""
    result: list[str] = []
    for line in (body or "").replace("\r", "").split("\n"):
        stripped = line.strip()
        if (stripped.startswith(">") or
                re.match(r"(?i)^on .{3,180} wrote:$", stripped) or
                re.match(r"(?i)^-{2,}\s*(original|forwarded) message\s*-{2,}$", stripped) or
                re.match(r"(?i)^begin forwarded message:$", stripped) or
                re.match(r"(?i)^from:\s*.+", stripped)):
            break
        result.append(line)
    return "\n".join(result).strip()


def _header(headers: list[dict[str, str]], name: str) -> str:
    return next((item["value"] for item in headers if item["name"].lower() == name.lower()), "")


def read_message(credentials: Credentials, message_id: str) -> dict[str, Any]:
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    payload = message.get("payload", {})
    plain_parts: list[str] = []
    html_parts: list[str] = []

    def collect_text(part: dict[str, Any]) -> None:
        mime_type = part.get("mimeType", "").lower()
        part_body = part.get("body", {})
        # Gmail may put larger MIME bodies behind an attachmentId rather than
        # including their base64 data in the message payload.
        if mime_type in ("text/plain", "text/html") and not part.get("filename"):
            data = part_body.get("data", "")
            if not data and part_body.get("attachmentId"):
                attachment = service.users().messages().attachments().get(
                    userId="me", messageId=message_id, id=part_body["attachmentId"]
                ).execute()
                data = attachment.get("data", "")
            if data:
                raw = base64.urlsafe_b64decode(data + "===").decode("utf-8", errors="replace")
                (plain_parts if mime_type == "text/plain" else html_parts).append(raw)
        for child in part.get("parts", []):
            collect_text(child)

    collect_text(payload)
    if plain_parts:
        decoded = "\n\n".join(plain_parts)
    else:
        html_body = "\n\n".join(html_parts)
        html_body = re.split(
            r"(?is)<div\b[^>]*class=[\"'][^\"']*(?:gmail_quote|yahoo_quoted)[^\"']*[\"'][^>]*>",
            html_body,
            maxsplit=1,
        )[0]
        html_body = re.sub(r"(?is)<blockquote\b[^>]*>", "\n> ", html_body)
        html_body = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1>", " ", html_body)
        html_body = re.sub(r"(?i)<\s*(br|/p|/div|/li|/tr)\b[^>]*>", "\n", html_body)
        decoded = re.sub(r"<[^>]+>", " ", html_body)
    decoded = unescape(decoded).replace("\r", "")
    decoded = re.sub(r"[ \t]+\n", "\n", decoded)
    decoded = re.sub(r"\n{3,}", "\n\n", decoded).strip()
    headers = payload.get("headers", [])
    return {
        "provider_message_id": message["id"], "thread_id": message.get("threadId"),
        "sender": _header(headers, "From"), "subject": _header(headers, "Subject"),
        # This field is used for classification and request review, so retain
        # the full message body rather than Gmail's short snippet.
        "body_preview": decoded or message.get("snippet", ""),
        "received_at": datetime.fromtimestamp(int(message.get("internalDate", "0")) / 1000, timezone.utc),
    }


def list_message_ids(credentials: Credentials, max_results: int | None = 25,
                     stop_at_known: set[str] | None = None) -> list[str]:
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    ids: list[str] = []
    page_token = None
    safe_limit = 25
    page_limit = safe_limit if max_results is None or max_results <= 0 else min(max_results, safe_limit)

    while True:
        request = service.users().messages().list(
            userId="me",
            labelIds=["INBOX"],
            pageToken=page_token,
            maxResults=page_limit,
        )
        response = request.execute()
        for item in response.get("messages", []):
            message_id = item["id"]
            if stop_at_known and message_id in stop_at_known:
                return ids
            ids.append(message_id)
            if isinstance(max_results, int) and max_results > 0 and len(ids) >= max_results:
                return ids[:max_results]
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return ids


def profile_email(credentials: Credentials) -> str:
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    return service.users().getProfile(userId="me").execute()["emailAddress"]


def send_reply(credentials: Credentials, to: str, subject: str, body: str, thread_id: str | None = None,
               html_body: str | None = None, reply_to_message_id: str | None = None) -> dict[str, Any]:
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    message = MIMEMultipart("alternative")
    message["To"] = to
    message["subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    message.attach(MIMEText(body, "plain", "utf-8"))
    if html_body:
        message.attach(MIMEText(html_body, "html", "utf-8"))
    if reply_to_message_id:
        original = service.users().messages().get(
            userId="me", id=reply_to_message_id, format="metadata",
            metadataHeaders=["Message-ID", "References"],
        ).execute()
        headers = original.get("payload", {}).get("headers", [])
        message_id = _header(headers, "Message-ID")
        references = _header(headers, "References")
        if message_id:
            message["In-Reply-To"] = message_id
            message["References"] = f"{references} {message_id}".strip()
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
    events = service.events()
    results: list[dict[str, Any]] = []
    page_token = None
    while True:
        response = events.list(
            calendarId="primary", timeMin=start.isoformat(), timeMax=end.isoformat(), q=query,
            singleEvents=True, orderBy="startTime", maxResults=2500, pageToken=page_token,
        ).execute()
        results.extend(response.get("items", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return results


def primary_calendar_timezone(credentials: Credentials) -> str:
    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    calendar = service.calendars().get(calendarId="primary").execute()
    return calendar.get("timeZone") or "UTC"


def move_event(credentials: Credentials, event_id: str, start: datetime, end: datetime, timezone_name: str = "UTC") -> dict[str, Any]:
    service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
    return service.events().patch(calendarId="primary", eventId=event_id, body={
        "start": {"dateTime": start.isoformat(), "timeZone": timezone_name},
        "end": {"dateTime": end.isoformat(), "timeZone": timezone_name},
    }, sendUpdates="all").execute()


async def run_sync(function, *args):
    return await asyncio.to_thread(function, *args)
