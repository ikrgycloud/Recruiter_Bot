import logging
import re
from difflib import SequenceMatcher
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parseaddr
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models.email_message import EmailMessage
from app.services.google_workspace import (find_events, latest_message_text, move_event,
                                           primary_calendar_timezone, run_sync, send_reply)

logger = logging.getLogger(__name__)


def canonical_timezone_name(value: str | None) -> str:
    """Convert fixed UTC offsets to usable IANA zones for calendar APIs."""
    name = (value or "UTC").strip()
    if name.upper() in {"UTC+05:30", "GMT+05:30", "+05:30"}:
        return "Asia/Kolkata"
    if name.upper() in {"UTC-00:00", "GMT-00:00", "+00:00", "-00:00"}:
        return "UTC"
    try:
        ZoneInfo(name)
        return name
    except ZoneInfoNotFoundError:
        return "UTC"


def requested_date(text: str, today: date) -> tuple[date | None, bool]:
    """Return the one unambiguous requested date; ambiguous wording needs review."""
    found: list[date] = []
    lowered = text.lower()
    relative = {"day after tomorrow": 2, "tomorrow": 1, "today": 0}
    for phrase, offset in relative.items():
        if re.search(rf"\b{re.escape(phrase)}\b", lowered):
            found.append(today + timedelta(days=offset))

    weekdays = {name.lower(): index for index, name in enumerate(
        ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"))}
    for match in re.finditer(r"\b(?:next\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", lowered):
        weekday = weekdays[match.group(1)]
        delta = (weekday - today.weekday()) % 7
        if delta == 0 or match.group(0).startswith("next "):
            delta = delta or 7
        found.append(today + timedelta(days=delta))

    text_without_ordinals = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", text, flags=re.IGNORECASE)
    patterns = (
        (r"\b\d{4}-\d{1,2}-\d{1,2}\b", ("%Y-%m-%d",)),
        (r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%m-%d-%y")),
        (r"\b\d{1,2}\s+[A-Za-z]+(?:,)?\s+\d{4}\b", ("%d %B %Y", "%d %b %Y", "%d %B, %Y", "%d %b, %Y")),
        (r"\b[A-Za-z]+\s+\d{1,2}(?:,)?\s+\d{4}\b", ("%B %d %Y", "%b %d %Y", "%B %d, %Y", "%b %d, %Y")),
        (r"\b\d{1,2}\s+[A-Za-z]+\b", ("%d %B", "%d %b")),
        (r"\b[A-Za-z]+\s+\d{1,2}\b", ("%B %d", "%b %d")),
    )
    ambiguous_numeric_date = False
    anchored: list[date] = []
    for pattern, formats in patterns:
        for match in re.finditer(pattern, text_without_ordinals, flags=re.IGNORECASE):
            value = None
            raw_date = match.group(0)
            for fmt in formats:
                if value:
                    break
                try:
                    parsed = datetime.strptime(raw_date.replace(",", ""), fmt)
                    value = parsed.date() if "%Y" in fmt or "%y" in fmt else parsed.date().replace(year=today.year)
                    break
                except ValueError:
                    continue
            if value:
                found.append(value)
                context = lowered[max(0, match.start() - 24):match.start()]
                if re.search(r"\b(to|on|for|available|free)\s+(?:the\s+)?$", context):
                    anchored.append(value)

    # Day/month without a year is safe when only one component can be the day.
    short_numeric = re.compile(r"\b\d{1,2}[/-]\d{1,2}\b(?![/-]\d)")
    for match in short_numeric.finditer(text_without_ordinals):
        first, second = (int(part) for part in re.split(r"[/-]", match.group(0)))
        try:
            if first > 12 and second <= 12:
                value = date(today.year, second, first)
            elif second > 12 and first <= 12:
                value = date(today.year, first, second)
            else:
                ambiguous_numeric_date = True
                continue
        except ValueError:
            ambiguous_numeric_date = True
            continue
        found.append(value)
        context = lowered[max(0, match.start() - 24):match.start()]
        if re.search(r"\b(to|on|for|available|free)\s+(?:the\s+)?$", context):
            anchored.append(value)

    unique = list(dict.fromkeys(found))
    anchored_unique = list(dict.fromkeys(anchored))
    # Positive availability constraints take priority over dates the candidate
    # says they cannot attend. “Available after 28 September” means the 29th.
    normalized_text = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", text, flags=re.IGNORECASE)
    date_literal = (
        r"(?:\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?|"
        r"\d{1,2}\s+[A-Za-z]+(?:,?\s+\d{2,4})?|"
        r"[A-Za-z]+\s+\d{1,2}(?:,?\s+\d{2,4})?)"
    )
    availability_dates: list[date] = []
    availability_pattern = re.compile(
        rf"\b(?:available|free)\s+(after|from|starting|on|for)\s+(?:the\s+)?({date_literal})",
        re.IGNORECASE,
    )
    for match in availability_pattern.finditer(normalized_text):
        raw_date = re.sub(r"\bsept\b", "Sep", match.group(2).replace(",", ""), flags=re.IGNORECASE)
        parsed_date = None
        for date_format in (
            "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%m-%d-%Y",
            "%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y",
            "%d %B", "%d %b", "%B %d", "%b %d",
        ):
            try:
                parsed = datetime.strptime(raw_date, date_format)
                parsed_date = parsed.date() if "%Y" in date_format else parsed.date().replace(year=today.year)
                if "%Y" not in date_format and parsed_date < today:
                    parsed_date = parsed_date.replace(year=today.year + 1)
                break
            except ValueError:
                continue
        if parsed_date:
            if match.group(1).lower() == "after":
                parsed_date += timedelta(days=1)
            availability_dates.append(parsed_date)
    if len(set(availability_dates)) == 1:
        return availability_dates[0], False
    if len(set(availability_dates)) > 1:
        return None, True
    if len(anchored_unique) == 1:
        return anchored_unique[0], False
    if ambiguous_numeric_date:
        return None, True
    return (unique[0], False) if len(unique) == 1 else (None, len(unique) > 1)


def match_calendar_event(events: list[dict], sender: str, body: str) -> tuple[dict | None, bool]:
    """Match by exact address first, then by a strong candidate name/alias match."""
    sender_email = parseaddr(sender or "")[1].strip().lower()
    exact = [event for event in events if sender_email and any(
        str(attendee.get("email", "")).strip().lower() == sender_email
        for attendee in event.get("attendees", [])
    ) and event.get("status") != "cancelled"]
    if len(exact) == 1:
        return exact[0], False
    if len(exact) > 1:
        return None, True

    def compact(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.lower())

    sender_name = parseaddr(sender or "")[0].strip()
    candidate_names = [sender_name] if sender_name and "@" not in sender_name else []
    signoff = re.search(
        r"(?is)(?:thank\s+you|thanks|regards|best\s+regards|sincerely)[,\s:;]*(.{1,100})$",
        body or "",
    )
    if signoff:
        for phrase in re.findall(r"\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,2}\b", signoff.group(1)):
            words = phrase.split()
            candidate_names.extend(" ".join(words[index:index + 2]) for index in range(len(words) - 1))
    sender_local = sender_email.partition("@")[0]
    local_key = re.sub(r"\d+$", "", compact(sender_local))
    name_keys = list(dict.fromkeys(compact(name) for name in candidate_names if compact(name)))

    ranked: list[tuple[int, dict]] = []
    for event in events:
        if event.get("status") == "cancelled":
            continue
        best = 0
        attendees = event.get("attendees", [])
        event_text = compact(str(event.get("summary", "")))
        for attendee in attendees:
            display = compact(str(attendee.get("displayName", "")))
            attendee_local = re.sub(r"\d+$", "", compact(str(attendee.get("email", "")).partition("@")[0]))
            if local_key and attendee_local == local_key:
                best = max(best, 92)
            for name_key in name_keys:
                if display and display == name_key:
                    best = max(best, 96)
                if attendee_local and attendee_local == name_key:
                    best = max(best, 92)
                if len(name_key) >= 10 and attendee_local and SequenceMatcher(None, name_key, attendee_local).ratio() >= 0.92:
                    best = max(best, 86)
                if len(name_key) >= 10 and event_text and name_key in event_text:
                    best = max(best, 84)
        ranked.append((best, event))
    ranked.sort(key=lambda item: item[0], reverse=True)
    if ranked and ranked[0][0] >= 84:
        if len(ranked) == 1 or ranked[0][0] - ranked[1][0] >= 8:
            return ranked[0][1], False
        return None, True
    return None, False


def requested_time(text: str) -> time | None:
    lowered = text.lower()
    change_phrase = r"\b(?:change|move|reschedule|schedule|shift|push|switch)\w*\b.{0,120}?\b(?:to|for)\s*"
    target_word = re.search(change_phrase + r"(noon|midnight)\b", lowered)
    if target_word:
        return time(12 if target_word.group(1) == "noon" else 0)

    target_24h = re.search(change_phrase + r"(?:around\s+)?([01]?\d|2[0-3]):([0-5]\d)\b", lowered)
    if target_24h:
        return time(int(target_24h.group(1)), int(target_24h.group(2)))

    clock_pattern = r"(\d{1,2})(?::(\d{2}))?\s*(a\.?m\.?|p\.?m\.?)"
    # Prefer the time following a change/reschedule instruction. Emails often
    # mention the existing time before the requested replacement time.
    target = re.search(change_phrase + rf"(?:around\s+)?{clock_pattern}\b", lowered)
    match = target or re.search(rf"\b(?:at\s*)?{clock_pattern}\b", lowered)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2) or 0)
        meridiem = match.group(3).replace(".", "")
        if hour < 1 or hour > 12 or minute > 59:
            return None
        hour = hour % 12 + (12 if meridiem == "pm" else 0)
        return time(hour, minute)
    match = re.search(r"\b(?:at\s*)?([01]?\d|2[0-3]):([0-5]\d)\b", lowered)
    if match:
        return time(int(match.group(1)), int(match.group(2)))
    if re.search(r"\bnoon\b", lowered):
        return time(12)
    if re.search(r"\bmidnight\b", lowered):
        return time(0)
    if re.search(r"\b(morning|early)\b", lowered):
        return time(9)
    if re.search(r"\b(afternoon|after lunch)\b", lowered):
        return time(13)
    if re.search(r"\b(evening)\b", lowered):
        return time(16)
    return None


def _event_datetime(value: dict, fallback_zone: ZoneInfo) -> datetime | None:
    raw = value.get("dateTime")
    if not raw:
        return None
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    zone_name = value.get("timeZone")
    if zone_name:
        try:
            return parsed.astimezone(ZoneInfo(zone_name))
        except ZoneInfoNotFoundError:
            pass
    return parsed.astimezone(fallback_zone)


async def build_reschedule_plan(
    message: EmailMessage,
    credentials,
    working_days: list[int] | None = None,
    shift_start: time = time(9),
    shift_end: time = time(17),
) -> dict:
    """Find one unambiguous interview and the next suitable free slot."""
    sender = parseaddr(message.sender or "")[1].strip().lower()
    if not sender:
        return {"status": "needs_review", "reason": "The sender address could not be identified."}

    received = message.received_at or datetime.now(timezone.utc)
    if received.tzinfo is None:
        received = received.replace(tzinfo=timezone.utc)
    window_start = received - timedelta(days=14)
    window_end = received + timedelta(days=365)
    candidates = await run_sync(find_events, credentials, window_start, window_end, None)
    body = f"{message.subject or ''}\n{latest_message_text(message.body_preview or '')}"
    event, ambiguous_event = match_calendar_event(candidates, message.sender or sender, body)
    original_start = _event_datetime(event.get("start", {}), ZoneInfo("UTC")) if event else None
    original_end = _event_datetime(event.get("end", {}), ZoneInfo("UTC")) if event else None
    if event and (not original_start or not original_end or original_end <= original_start):
        return {"status": "needs_review", "reason": "The linked calendar event has no supported meeting time."}
    if event:
        timezone_name = canonical_timezone_name(
            getattr(original_start.tzinfo, "key", None) or str(original_start.tzinfo)
        )
    else:
        timezone_name = canonical_timezone_name(await run_sync(primary_calendar_timezone, credentials))
    schedule_zone = ZoneInfo(timezone_name)
    if event:
        original_start = original_start.astimezone(schedule_zone)
        original_end = original_end.astimezone(schedule_zone)
        duration = original_end - original_start
        if duration > timedelta(hours=8):
            return {"status": "needs_review", "reason": "The linked calendar event duration needs manual review."}
    else:
        # Keep a useful availability suggestion visible even when an alias
        # prevents a safe automatic link to the existing event.
        duration = timedelta(hours=1)

    event_context = {
        **({"event_id": event["id"]} if event else {}),
        "event_summary": event.get("summary", "Interview") if event else "Interview",
        "timezone": timezone_name, "duration_seconds": int(duration.total_seconds()),
        "candidate_email": sender,
    }
    if not event:
        event_context["reason"] = (
            "Several calendar events could match this request. Review the interview before confirming."
            if ambiguous_event else
            "Suggested time is based on calendar availability. Review the existing interview before confirming."
        )
    if datetime.now(timezone.utc) - received.astimezone(timezone.utc) > timedelta(days=7):
        return {"status": "needs_review", **event_context,
                "reason": "This request is more than seven days old and needs a fresh human review."}
    local_today = datetime.now(schedule_zone).date()
    desired_date, ambiguous = requested_date(body, local_today)
    has_requested_date = desired_date is not None
    if ambiguous:
        return {"status": "needs_review", **event_context, "reason": "The email mentions multiple possible dates."}
    if desired_date is None:
        desired_date = local_today + timedelta(days=1)
    if desired_date < local_today:
        return {"status": "needs_review", **event_context, "reason": "The requested date has already passed."}
    allowed_days = set(range(5) if working_days is None else working_days)
    if not allowed_days or shift_end <= shift_start:
        return {"status": "needs_review", **event_context,
                "reason": "Set at least one working day and a valid shift in Rescheduling Settings."}

    requested_clock = requested_time(body) or (
        original_start.timetz().replace(tzinfo=None) if original_start else shift_start
    )
    requested_clock_label = requested_clock.strftime("%H:%M")
    # On the requested date, start at the candidate's requested time. If that
    # time conflicts, only search later slots that day. Later working days start
    # at the shift opening. This avoids suggesting a time before the candidate
    # asked for when their preferred time is already busy.
    for day_offset in range(31):
        day = desired_date + timedelta(days=day_offset)
        if day.weekday() not in allowed_days:
            continue
        day_start = datetime.combine(day, time(0), tzinfo=schedule_zone)
        day_end = day_start + timedelta(days=1)
        events = await run_sync(find_events, credentials, day_start, day_end, None)
        busy: list[tuple[datetime, datetime]] = []
        for other in events:
            if (event and other.get("id") == event.get("id")) or other.get("status") == "cancelled":
                continue
            start = _event_datetime(other.get("start", {}), schedule_zone)
            end = _event_datetime(other.get("end", {}), schedule_zone)
            if start and end and end > start:
                busy.append((start, end))
            elif other.get("start", {}).get("date"):
                # Treat all-day events as unavailable for automatic movement.
                busy.append((day_start, day_end))

        minute = shift_start.hour * 60 + shift_start.minute
        if day == desired_date:
            minute = max(minute, requested_clock.hour * 60 + requested_clock.minute)
        latest_start = shift_end.hour * 60 + shift_end.minute - int(duration.total_seconds() // 60)
        while minute <= latest_start:
            proposed = datetime.combine(day, time(minute // 60, minute % 60), tzinfo=schedule_zone)
            proposed_end = proposed + duration
            if not any(proposed < busy_end and proposed_end > busy_start for busy_start, busy_end in busy):
                chosen = proposed
                break
            minute += 30
        else:
            chosen = None
        if chosen:
            return {
                "status": "ready" if event else "needs_review",
                **({"event_id": event["id"]} if event else {}),
                "event_summary": event.get("summary", "Interview") if event else "Interview",
                "duration_seconds": int(duration.total_seconds()),
                "requested_date": desired_date.isoformat(), "candidate_requested_date": has_requested_date,
                "candidate_requested_time": requested_clock_label,
                "start": chosen.isoformat(),
                "end": (chosen + duration).isoformat(), "timezone": timezone_name,
                "availability_date": day.isoformat(), "used_next_available_date": day != desired_date,
                "candidate_email": sender,
                **({} if event else {"reason": event_context["reason"]}),
            }
    return {"status": "needs_review", **event_context, "reason": "No slot was available within the configured working days and shift in the next 30 days."}


async def execute_reschedule_plan(session, message: EmailMessage, credentials, plan: dict) -> dict:
    """Move the event, then confirm the change to the candidate by email."""
    if plan.get("status") != "ready":
        return plan
    event = await run_sync(
        move_event, credentials, plan["event_id"], datetime.fromisoformat(plan["start"]),
        datetime.fromisoformat(plan["end"]), plan["timezone"],
    )
    message.processed = True
    await session.commit()
    plan = {
        **plan,
        "status": "rescheduled",
        "event_id": event.get("id", plan["event_id"]),
        "calendar_updated": True,
        "google_calendar_event_url": event.get("htmlLink"),
    }
    if plan.get("candidate_email"):
        try:
            event_zone = ZoneInfo(canonical_timezone_name(plan.get("timezone")))
            scheduled_start = datetime.fromisoformat(plan["start"]).astimezone(event_zone)
            scheduled_end = datetime.fromisoformat(plan["end"]).astimezone(event_zone)
            readable_date = scheduled_start.strftime("%A, %B %d, %Y")
            readable_start = scheduled_start.strftime("%I:%M %p").lstrip("0")
            readable_end = scheduled_end.strftime("%I:%M %p").lstrip("0")
            timezone_label = scheduled_start.tzname() or canonical_timezone_name(plan.get("timezone"))
            duration_minutes = max(1, int((scheduled_end - scheduled_start).total_seconds() // 60))
            duration_hours, remaining_minutes = divmod(duration_minutes, 60)
            duration_label = (f"{duration_hours} hour{'s' if duration_hours != 1 else ''}"
                              if duration_hours else "")
            if remaining_minutes:
                duration_label = (duration_label + " " if duration_label else "") + f"{remaining_minutes} minutes"
        except ValueError:
            readable_date, readable_start, readable_end = plan["start"], "", ""
            timezone_label, duration_label = plan.get("timezone", "UTC"), ""
        candidate_name = parseaddr(message.sender or "")[0].strip()
        greeting = f"Hi {candidate_name}," if candidate_name else "Hello,"
        title = plan.get("event_summary") or "Interview"
        plain_body = (
            f"{greeting}\n\n"
            "Your interview has been rescheduled. The updated meeting is in your calendar invitation.\n\n"
            f"Interview: {title}\n"
            f"Date: {readable_date}\n"
            f"Time: {readable_start} to {readable_end} {timezone_label}\n"
            + (f"Requested time: {plan['candidate_requested_time']} {timezone_label}\n" if plan.get("candidate_requested_time") else "")
            + (f"Duration: {duration_label}\n" if duration_label else "")
            + "\nIf this time does not work for you, reply to this email and let us know.\n\n"
              "Best regards,\nRecruiting Team"
        )
        safe_title = escape(title)
        safe_name = escape(candidate_name) if candidate_name else ""
        html_body = (
            f"<p>{'Hi ' + safe_name + ',' if safe_name else 'Hello,'}</p>"
            "<p>Your interview has been rescheduled. The updated meeting is in your calendar invitation.</p>"
            "<table role=\"presentation\" cellpadding=\"6\" cellspacing=\"0\" "
            "style=\"border-collapse:collapse;margin:16px 0\">"
            f"<tr><td><strong>Interview</strong></td><td>{safe_title}</td></tr>"
            f"<tr><td><strong>Date</strong></td><td>{escape(readable_date)}</td></tr>"
            f"<tr><td><strong>Time</strong></td><td>{escape(readable_start)} to {escape(readable_end)} "
            f"{escape(timezone_label)}</td></tr>"
            + (f"<tr><td><strong>Requested time</strong></td><td>{escape(plan['candidate_requested_time'])} {escape(timezone_label)}</td></tr>" if plan.get("candidate_requested_time") else "")
            + (f"<tr><td><strong>Duration</strong></td><td>{escape(duration_label)}</td></tr>" if duration_label else "")
            + "</table><p>If this time does not work for you, reply to this email and let us know.</p>"
              "<p>Best regards,<br>Recruiting Team</p>"
        )
        try:
            await run_sync(
                send_reply, credentials, plan["candidate_email"], message.subject or "Interview rescheduled",
                plain_body, message.thread_id, html_body, message.provider_message_id,
            )
            plan["candidate_notified"] = True
        except Exception:
            logger.exception("Calendar event moved but the candidate confirmation could not be sent")
            plan["candidate_notified"] = False
            plan["notification_error"] = "The calendar was updated, but the confirmation email could not be sent. Check Gmail before retrying."
    return plan


async def slot_is_available(credentials, event_id: str, start: datetime, end: datetime) -> bool:
    events = await run_sync(find_events, credentials, start, end, None)
    for other in events:
        if other.get("id") == event_id or other.get("status") == "cancelled":
            continue
        other_start = _event_datetime(other.get("start", {}), start.tzinfo or ZoneInfo("UTC"))
        other_end = _event_datetime(other.get("end", {}), start.tzinfo or ZoneInfo("UTC"))
        if other_start and other_end and start < other_end and end > other_start:
            return False
        if other.get("start", {}).get("date"):
            return False
    return True


def slot_matches_work_schedule(
    start: datetime,
    end: datetime,
    timezone_name: str,
    working_days: list[int],
    shift_start: time,
    shift_end: time,
) -> bool:
    zone = ZoneInfo(canonical_timezone_name(timezone_name))
    local_start = start.astimezone(zone)
    local_end = end.astimezone(zone)
    if local_start.date() != local_end.date() or local_start.weekday() not in working_days:
        return False
    shift_open = datetime.combine(local_start.date(), shift_start, tzinfo=zone)
    shift_close = datetime.combine(local_start.date(), shift_end, tzinfo=zone)
    return local_start >= shift_open and local_end <= shift_close
