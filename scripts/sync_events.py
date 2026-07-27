#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import sys
import unicodedata
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import recurring_ical_events
import requests
import yaml
from bs4 import BeautifulSoup
from icalendar import Calendar

TIMEZONE_NAME = os.getenv("EVENT_TIMEZONE", "America/New_York")
TIMEZONE = ZoneInfo(TIMEZONE_NAME)
LOOKAHEAD_DAYS = int(os.getenv("EVENT_LOOKAHEAD_DAYS", "180"))
MAX_EVENTS = int(os.getenv("EVENT_MAX_EVENTS", "100"))
DEFAULT_IMAGE = os.getenv("EVENT_DEFAULT_IMAGE", "").strip()

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "registry" / "events-live.yaml"
INDEX_PATH = ROOT / "knowledge" / "events" / "upcoming-events.md"
GENERATED_DIR = ROOT / "knowledge" / "events" / "generated"

LOCATION_ALIASES = {
    "urbancrest": "Urbancrest Church",
    "urbancrest baptist church": "Urbancrest Church",
    "urbancrest at lebanon": "Urbancrest Church",
    "gym": "Urbancrest Church Gymnasium",
    "gymnasium": "Urbancrest Church Gymnasium",
    "urbancrest gym": "Urbancrest Church Gymnasium",
    "worship center": "Urbancrest Church Worship Center",
    "sanctuary": "Urbancrest Church Worship Center",
}

MINISTRY_RULES = {
    "kids": ["kid", "kids", "child", "children", "awana", "vbs", "preschool"],
    "students": ["student", "students", "youth", "middle school", "high school"],
    "missions": ["mission", "missions", "outreach", "serve day"],
    "men": ["men's", "mens", "men "],
    "women": ["women's", "womens", "women "],
    "worship": ["worship", "choir", "concert", "music"],
    "small_groups": ["small group", "small groups", "bible study", "bible studies"],
    "sports": ["golf", "football", "baseball", "sports", "cruise-in"],
    "care": ["grief", "recovery", "support group", "benevolence"],
}

AUDIENCE_RULES = {
    "children": ["kid", "kids", "child", "children", "awana", "vbs", "preschool"],
    "students": ["student", "students", "youth", "middle school", "high school"],
    "men": ["men's", "mens", "men "],
    "women": ["women's", "womens", "women "],
    "families": ["family", "families", "parent", "parents"],
    "volunteers": ["volunteer", "serve", "serving"],
    "seniors": ["senior adult", "seniors"],
}


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = html.unescape(str(value))
    text = text.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";")
    text = BeautifulSoup(text, "html.parser").get_text("\n")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_for_matching(value: str) -> str:
    return (
        value.casefold()
        .replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("—", "-")
    )


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


def utc_sort_value(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def stable_event_id(uid: str, recurrence_id: str, start: datetime) -> str:
    source = f"{uid}|{recurrence_id}|{start.isoformat()}"
    return "event-" + hashlib.sha256(source.encode("utf-8")).hexdigest()[:16]


def slugify(value: str, max_length: int = 72) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:max_length].rstrip("-") or "event"


def normalize_location(value: str) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        return ""
    return LOCATION_ALIASES.get(cleaned.casefold(), cleaned)


def extract_urls(*values: str) -> list[str]:
    found: list[str] = []
    pattern = re.compile(r"https?://[^\s<>()\]\[\"']+")
    for value in values:
        for match in pattern.findall(value or ""):
            url = match.rstrip(".,;:)")
            if url not in found:
                found.append(url)
    return found


def classify_urls(urls: list[str]) -> tuple[str | None, str | None]:
    registration = None
    info = None
    for url in urls:
        host = urlparse(url).netloc.lower()
        lower = url.lower()
        if (
            "churchcenter.com/registrations" in lower
            or "churchcenter.com/people/forms" in lower
            or "register" in lower
            or "signup" in lower
        ):
            registration = registration or url
        elif host:
            info = info or url
    return registration, info


def extract_image(component, description: str) -> str | None:
    candidates: list[str] = []

    for key in ("ATTACH", "IMAGE"):
        raw = component.get(key)
        if raw:
            values = raw if isinstance(raw, list) else [raw]
            candidates.extend(str(v) for v in values)

    x_alt_desc = clean_text(component.get("X-ALT-DESC"))
    candidates.extend(extract_urls(description, x_alt_desc))

    for url in candidates:
        clean = url.strip()
        if clean.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            return clean

    return DEFAULT_IMAGE or None


def infer_labels(title: str, description: str) -> tuple[list[str], list[str]]:
    haystack = normalize_for_matching(f"{title}\n{description}")

    ministries = [
        ministry
        for ministry, terms in MINISTRY_RULES.items()
        if any(normalize_for_matching(term) in haystack for term in terms)
    ]
    audiences = [
        audience
        for audience, terms in AUDIENCE_RULES.items()
        if any(normalize_for_matching(term) in haystack for term in terms)
    ]

    return ministries or ["churchwide"], audiences or ["everyone"]


def annotate_chronology(events: list[dict[str, object]]) -> None:
    seen_ministries: set[str] = set()
    seen_audiences: set[str] = set()

    for rank, event in enumerate(events, start=1):
        event["chronological_rank"] = rank
        event["next_for_ministries"] = []
        event["next_for_audiences"] = []

        for ministry in event["ministries"]:
            ministry = str(ministry)
            if ministry != "churchwide" and ministry not in seen_ministries:
                event["next_for_ministries"].append(ministry)
                seen_ministries.add(ministry)

        for audience in event["audiences"]:
            audience = str(audience)
            if audience != "everyone" and audience not in seen_audiences:
                event["next_for_audiences"].append(audience)
                seen_audiences.add(audience)


def format_day(dt: datetime) -> str:
    return dt.strftime("%A, %B %-d, %Y")


def format_time(dt: datetime) -> str:
    return dt.strftime("%-I:%M %p").replace(":00 ", " ")


def display_when(start: datetime, end: datetime, all_day: bool) -> str:
    if all_day:
        final_day = end - timedelta(days=1)
        if final_day.date() > start.date():
            return f"{format_day(start)} through {format_day(final_day)}"
        return format_day(start)

    if start.date() == end.date():
        return f"{format_day(start)}, {format_time(start)} to {format_time(end)}"

    return (
        f"{format_day(start)} at {format_time(start)} through "
        f"{format_day(end)} at {format_time(end)}"
    )


def make_summary(title: str, when: str, location: str, description: str) -> str:
    if description:
        first = re.split(r"(?<=[.!?])\s+", description.strip())[0]
        first = first[:220].rstrip()
        if len(description) > 220:
            first += "..."
        return first

    if location:
        return f"{title} is scheduled for {when} at {location}."
    return f"{title} is scheduled for {when}."


def yaml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def yaml_inline_list(values: list[object]) -> str:
    return "[" + ", ".join(str(value) for value in values) + "]"


def write_event_article(event: dict[str, object], generated_at: str) -> str:
    start: datetime = event["_start_dt"]
    title = str(event["title"])
    date_prefix = start.strftime("%Y-%m-%d")
    slug = f"{date_prefix}-{slugify(title)}-{str(event['id'])[-6:]}"
    relative_path = f"knowledge/events/generated/{slug}.md"
    path = ROOT / relative_path

    tags = ["event", "calendar", "upcoming"]
    tags.extend(str(x) for x in event["ministries"])
    tags.extend(str(x) for x in event["audiences"])
    tags = list(dict.fromkeys(tags))

    lines = [
        "---",
        f"id: events.live.{event['id']}",
        "version: 1.3",
        "status: published",
        "priority: 90",
        f"title: {yaml_quote(title)}",
        f"summary: {yaml_quote(str(event['summary']))}",
        "category: [events]",
        "intent:",
        "  primary: event_details",
        "  secondary: [upcoming_events, calendar, schedule, registration, next_ministry_event]",
        "audience: " + yaml_inline_list(event["audiences"]),
        "ministries: " + yaml_inline_list(event["ministries"]),
        "answer_style: helpful",
        "confidence: high",
        "owner:",
        "  ministry: church_office",
        "review:",
        "  doctrinal: not_required",
        "  factual: automated",
        "tags: " + yaml_inline_list(tags),
        "search_terms:",
        f"  - {yaml_quote(title)}",
        f"  - {yaml_quote('When is ' + title + '?')}",
        f"  - {yaml_quote('Where is ' + title + '?')}",
        f"  - {yaml_quote('Tell me about ' + title)}",
        f"  - {yaml_quote('How do I register for ' + title + '?')}",
        "resources:",
        "  - events.live",
        f"event_id: {event['id']}",
        f"event_start: {yaml_quote(str(event['start']))}",
        f"event_end: {yaml_quote(str(event['end']))}",
        f"sort_start_utc: {yaml_quote(str(event['sort_start_utc']))}",
        f"sort_end_utc: {yaml_quote(str(event['sort_end_utc']))}",
        f"chronological_rank: {event['chronological_rank']}",
        "next_for_ministries: " + yaml_inline_list(event["next_for_ministries"]),
        "next_for_audiences: " + yaml_inline_list(event["next_for_audiences"]),
        f"all_day: {'true' if event['all_day'] else 'false'}",
    ]

    if event.get("registration_url"):
        lines.append(f"registration_url: {yaml_quote(str(event['registration_url']))}")
    if event.get("info_url"):
        lines.append(f"info_url: {yaml_quote(str(event['info_url']))}")
    if event.get("image_url"):
        lines.append(f"image_url: {yaml_quote(str(event['image_url']))}")
    if event.get("location"):
        lines.append(f"location: {yaml_quote(str(event['location']))}")

    lines.extend([
        f"last_generated: {generated_at}",
        "---",
        "",
        f"# {title}",
        "",
        str(event["summary"]),
        "",
        f"**When:** {event['display_when']}",
        "",
    ])

    if event.get("location"):
        lines.extend([f"**Where:** {event['location']}", ""])
    if event.get("description"):
        lines.extend([str(event["description"]), ""])
    if event.get("registration_url"):
        lines.extend([f"**Registration:** {event['registration_url']}", ""])
    elif event.get("info_url"):
        lines.extend([f"**More information:** {event['info_url']}", ""])
    if event.get("image_url"):
        lines.extend([f"**Event image:** {event['image_url']}", ""])

    lines.extend([
        "This information is synchronized automatically from Urbancrest's live calendar.",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
    return relative_path


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
        headers={"User-Agent": "Urbancrest-Knowledge-Event-Sync/1.3"},
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
        location = normalize_location(clean_text(component.get("LOCATION")))
        uid = clean_text(component.get("UID")) or title
        recurrence_id = clean_text(component.get("RECURRENCE-ID"))

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

        component_url = clean_text(component.get("URL"))
        urls = extract_urls(
            component_url,
            description,
            clean_text(component.get("X-ALT-DESC")),
        )
        registration_url, info_url = classify_urls(urls)
        image_url = extract_image(component, description)
        ministries, audiences = infer_labels(title, description)
        when = display_when(start, end, all_day)
        summary = make_summary(title, when, location, description)

        events.append({
            "id": stable_event_id(uid, recurrence_id, start),
            "uid": uid,
            "title": title,
            "summary": summary,
            "start": iso_value(start, all_day),
            "end": iso_value(end, all_day),
            "sort_start_utc": utc_sort_value(start),
            "sort_end_utc": utc_sort_value(end),
            "display_when": when,
            "all_day": all_day,
            "location": location or None,
            "description": description or None,
            "registration_url": registration_url,
            "info_url": info_url,
            "image_url": image_url,
            "ministries": ministries,
            "audiences": audiences,
            "status": status.lower(),
            "_start_dt": start,
            "_end_dt": end,
        })

    events.sort(key=lambda item: (item["_start_dt"], str(item["title"]).casefold()))
    events = events[:MAX_EVENTS]
    annotate_chronology(events)
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if GENERATED_DIR.exists():
        shutil.rmtree(GENERATED_DIR)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    for event in events:
        event["knowledge_file"] = write_event_article(event, generated_at)

    registry_events = [
        {k: v for k, v in event.items() if not k.startswith("_") and v is not None}
        for event in events
    ]

    registry = {
        "version": "1.3",
        "generated_at": generated_at,
        "timezone": TIMEZONE_NAME,
        "source": "planning_center_ical",
        "source_of_truth_for_calendar_intents": True,
        "sort_order": "sort_start_utc_ascending",
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
        "version: 1.3",
        "status: published",
        "priority: 100",
        "title: Upcoming Events",
        "summary: Live upcoming events synchronized from the Urbancrest calendar.",
        "category: [events]",
        "intent:",
        "  primary: upcoming_events",
        "  secondary: [calendar, schedule, whats_happening, next_ministry_event]",
        "audience: [everyone]",
        "answer_style: helpful",
        "confidence: high",
        "owner:",
        "  ministry: church_office",
        "review:",
        "  doctrinal: not_required",
        "  factual: automated",
        "tags: [events, calendar, upcoming, schedule]",
        "resources:",
        "  - events.live",
        "calendar_sort_order: sort_start_utc_ascending",
        f"last_generated: {generated_at}",
        "---",
        "",
        "# Upcoming Events",
        "",
        "This page is generated automatically from Urbancrest's live calendar.",
        "Events are listed in ascending chronological order.",
        "",
    ]

    if not events:
        lines.extend(["There are currently no upcoming events listed in the calendar.", ""])
    else:
        for event in events:
            lines.extend([
                f"## {event['title']}",
                "",
                str(event["summary"]),
                "",
                f"**When:** {event['display_when']}",
                "",
            ])
            if event.get("location"):
                lines.extend([f"**Where:** {event['location']}", ""])
            if event.get("registration_url"):
                lines.extend([f"**Registration:** {event['registration_url']}", ""])
            elif event.get("info_url"):
                lines.extend([f"**More information:** {event['info_url']}", ""])
            lines.extend([f"Detailed event file: `{event['knowledge_file']}`", ""])

    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    print(f"Wrote {len(events)} events.")
    print("Calendar registry sort order: sort_start_utc ascending.")
    print(f"Generated directory: {GENERATED_DIR.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
