#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yaml
from icalendar import Calendar
import recurring_ical_events

TIMEZONE = ZoneInfo("America/New_York")
LOOKAHEAD_DAYS = int(os.getenv("EVENT_LOOKAHEAD_DAYS", "120"))
MAX_EVENTS = int(os.getenv("EVENT_MAX_EVENTS", "75"))

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "registry" / "events-live.yaml"
ARTICLE_PATH = ROOT / "knowledge" / "events" / "upcoming-events.md"


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = text.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";")
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def as_local_datetime(value: object) -> tuple[datetime, bool]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=TIMEZONE)
        return value.astimezone(TIMEZONE), False

    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=TIMEZONE), True

    raise TypeError(f"Unsupported calendar date value: {type(value)!r}")


def iso_value(dt: datetime, all_day: bool) -> str:
    return dt.date().isoformat() if all_day else dt.isoformat()


def event_id(uid: str, start: datetime) -> str:
    digest = hashlib.sha256(f"{uid}|{start.isoformat()}".encode("utf-8")).hexdigest()[:16]
    return f"event-{digest}"


def format_day(dt: datetime) -> str:
    return dt.strftime("%A, %B %-d, %Y")


def format_time(dt: datetime) -> str:
    value = dt.strftime("%-I:%M %p")
    return value.replace(":00 ", " ")


def format_event_time(start: datetime, end: datetime, all_day: bool) -> str:
    if all_day:
        final_day = end - timedelta(days=1)
        if final_day.date() > start.date():
            return f"{format_day(start)} through {format_day(final_day)}"
        return format_day(start)

    if start.date() == end.date():
        if start.time() == end.time():
            return f"{format_day(start)} at {format_time(start)}"
        return f"{format_day(start)}, {format_time(start)}–{format_time(end)}"

    return (
        f"{format_day(start)} at {format_time(start)} through "
        f"{format_day(end)} at {format_time(end)}"
    )


def main() -> int:
    feed_url = os.getenv("ICAL_FEED_URL", "").strip()
    if not feed_url:
        print("ICAL_FEED_URL is not set.", file=sys.stderr)
        return 1

    if feed_url.startswith("webcal://"):
        feed_url = "https://" + feed_url[len("webcal://"):]

    response = requests.get(
        feed_url,
        timeout=30,
        headers={"User-Agent": "Urbancrest-Knowledge-Event-Sync/1.0"},
    )
    response.raise_for_status()

    calendar = Calendar.from_ical(response.content)
    now = datetime.now(TIMEZONE)
    window_start = now - timedelta(days=1)
    window_end = now + timedelta(days=LOOKAHEAD_DAYS)

    components = recurring_ical_events.of(calendar).between(window_start, window_end)
    events: list[dict[str, object]] = []

    for component in components:
        status = clean_text(component.get("STATUS", "CONFIRMED")).upper()
        if status == "CANCELLED":
            continue

        title = clean_text(component.get("SUMMARY")) or "Untitled Event"
        description = clean_text(component.get("DESCRIPTION"))
        location = clean_text(component.get("LOCATION"))
        url = clean_text(component.get("URL"))
        uid = clean_text(component.get("UID")) or title

        start, all_day = as_local_datetime(component.decoded("DTSTART"))

        if component.get("DTEND") is not None:
            end, end_all_day = as_local_datetime(component.decoded("DTEND"))
            all_day = all_day and end_all_day
        elif component.get("DURATION") is not None:
            end = start + component.decoded("DURATION")
        else:
            end = start + (timedelta(days=1) if all_day else timedelta(hours=1))

        if end < now:
            continue

        events.append(
            {
                "id": event_id(uid, start),
                "title": title,
                "start": iso_value(start, all_day),
                "end": iso_value(end, all_day),
                "all_day": all_day,
                "location": location or None,
                "description": description or None,
                "url": url or None,
                "status": status.lower(),
                "_start_dt": start,
                "_end_dt": end,
            }
        )

    events.sort(key=lambda item: item["_start_dt"])
    events = events[:MAX_EVENTS]
    generated_at = datetime.now(timezone.utc).isoformat()

    registry_events = [
        {k: v for k, v in event.items() if not k.startswith("_") and v is not None}
        for event in events
    ]

    registry = {
        "version": "1.0",
        "generated_at": generated_at,
        "timezone": "America/New_York",
        "source": "planning_center_ical",
        "lookahead_days": LOOKAHEAD_DAYS,
        "event_count": len(registry_events),
        "events": registry_events,
    }

    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(
        yaml.safe_dump(registry, sort_keys=False, allow_unicode=True, width=1000),
        encoding="utf-8",
    )

    lines = [
        "---",
        "id: events.upcoming.live",
        "version: 1.0",
        "status: published",
        "priority: 100",
        "title: Upcoming Events",
        "summary: Live upcoming events synchronized from the Urbancrest calendar.",
        "category: [events]",
        "intent:",
        "  primary: upcoming_events",
        "  secondary: [calendar, schedule, whats_happening]",
        "audience: [everyone]",
        "answer_style: helpful",
        "confidence: high",
        "owner:",
        "  ministry: church_office",
        "review:",
        "  doctrinal: not_required",
        "  factual: automated",
        "tags: [events, calendar, upcoming, schedule]",
        "search_terms:",
        "  - What events are coming up?",
        "  - What is happening at Urbancrest?",
        "  - Church calendar",
        "  - Upcoming activities",
        "resources:",
        "  - events.live",
        f"last_generated: {generated_at}",
        "---",
        "",
        "# Upcoming Events",
        "",
        "This page is generated automatically from Urbancrest's live calendar.",
        "",
    ]

    if not events:
        lines.extend(["There are currently no upcoming events listed in the calendar.", ""])
    else:
        for event in events:
            lines.extend(
                [
                    f"## {event['title']}",
                    "",
                    f"**{format_event_time(event['_start_dt'], event['_end_dt'], bool(event['all_day']))}**",
                    "",
                ]
            )
            if event.get("location"):
                lines.extend([f"**Location:** {event['location']}", ""])
            if event.get("description"):
                lines.extend([str(event["description"]), ""])
            if event.get("url"):
                lines.extend([f"More information: {event['url']}", ""])

    ARTICLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTICLE_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print(f"Wrote {len(events)} events.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
