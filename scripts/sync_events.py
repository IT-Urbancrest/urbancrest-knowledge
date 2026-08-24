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
from collections import defaultdict
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
LOOKAHEAD_DAYS = int(os.getenv("EVENT_LOOKAHEAD_DAYS", "365"))
MAX_MAIN_EVENTS = int(
    os.getenv("EVENT_MAX_MAIN_EVENTS", os.getenv("EVENT_MAX_EVENTS", "150"))
)
MAX_SMALL_GROUP_SERIES = int(os.getenv("SMALL_GROUP_MAX_SERIES", "100"))
MAX_SMALL_GROUP_OCCURRENCES = int(os.getenv("SMALL_GROUP_MAX_OCCURRENCES", "12"))
DEFAULT_IMAGE = os.getenv("EVENT_DEFAULT_IMAGE", "").strip()

PLANNING_CENTER_API_BASE = os.getenv(
    "PLANNING_CENTER_API_BASE",
    "https://api.planningcenteronline.com",
).rstrip("/")
PLANNING_CENTER_API_VERSION = os.getenv(
    "PLANNING_CENTER_API_VERSION",
    "2026-06-22",
).strip()
PLANNING_CENTER_APP_ID = os.getenv("PLANNING_CENTER_APP_ID", "").strip()
PLANNING_CENTER_SECRET = os.getenv("PLANNING_CENTER_SECRET", "").strip()
PLANNING_CENTER_API_MAX_PAGES = int(
    os.getenv("PLANNING_CENTER_API_MAX_PAGES", "50")
)
PLANNING_CENTER_UID_PATTERN = re.compile(
    r"^ET-(?P<event_time_id>\d+)-(?P<event_instance_id>\d+)@",
    flags=re.IGNORECASE,
)

ROOT = Path(__file__).resolve().parents[1]

EVENT_REGISTRY_PATH = ROOT / "registry" / "events-live.yaml"
GROUP_REGISTRY_PATH = ROOT / "registry" / "small-groups-live.yaml"
CATEGORY_RULES_PATH = ROOT / "registry" / "event-categories.yaml"
OVERRIDES_PATH = ROOT / "registry" / "event-overrides.yaml"

EVENT_INDEX_PATH = ROOT / "knowledge" / "events" / "upcoming-events.md"
EVENT_GENERATED_DIR = ROOT / "knowledge" / "events" / "generated"

GROUP_INDEX_PATH = ROOT / "knowledge" / "small-groups" / "upcoming-small-groups.md"
GROUP_GENERATED_DIR = ROOT / "knowledge" / "small-groups" / "generated"

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
    "small_groups": [
        "small group", "small groups", "community group",
        "life group", "home group", "growth group",
    ],
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
    text = text.replace("\u2014", "-")
    text = text.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";")
    if re.search(r"<[^>]+>", text):
        text = BeautifulSoup(text, "html.parser").get_text("\n")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


DETAIL_PROPERTY_NAMES = (
    "X-ALT-DESC",
    "X-PLANNING-CENTER-DESCRIPTION",
    "X-PLANNING-CENTER-DETAILS",
    "X-PCO-DESCRIPTION",
    "X-PCO-DETAILS",
    "DETAILS",
)


def component_text_values(component, key: str) -> list[str]:
    raw = component.get(key)
    if raw is None:
        return []
    values = raw if isinstance(raw, list) else [raw]
    return [cleaned for value in values if (cleaned := clean_text(value))]


def normalized_content(value: str) -> str:
    return re.sub(r"\s+", " ", normalize_for_matching(value)).strip()


def extract_details(component, description: str) -> str:
    """
    Extract a separate public details/rich-description field when the iCal
    feed includes one.

    Planning Center's plain iCal description is read from DESCRIPTION. Rich or
    alternate details may be exported in X-ALT-DESC or another public custom
    property. Duplicate copies of DESCRIPTION are discarded.
    """
    property_names = list(DETAIL_PROPERTY_NAMES)

    # Future-proof the parser for public Planning Center custom properties.
    for key in component.keys():
        name = str(key).upper()
        if (
            name.startswith("X-")
            and any(token in name for token in ("DETAIL", "DESCRIPTION", "DESC"))
            and "INTERNAL" not in name
            and "NOTE" not in name
            and name not in property_names
        ):
            property_names.append(name)

    description_normalized = normalized_content(description)
    details: list[str] = []
    seen: set[str] = set()

    for property_name in property_names:
        for candidate in component_text_values(component, property_name):
            candidate_normalized = normalized_content(candidate)
            if not candidate_normalized or candidate_normalized == description_normalized:
                continue

            # X-ALT-DESC may contain the plain description followed by richer
            # details. Remove the repeated leading description when possible.
            if description and candidate.startswith(description):
                candidate = candidate[len(description):].lstrip(" \t\r\n:-")
                candidate_normalized = normalized_content(candidate)

            if not candidate_normalized or candidate_normalized in seen:
                continue

            seen.add(candidate_normalized)
            details.append(candidate)

    return "\n\n".join(details).strip()


def normalize_for_matching(value: str) -> str:
    return (
        value.casefold()
        .replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
        .replace("–", "-")
        .replace("\u2014", "-")
    )


def parse_planning_center_uid(uid: str) -> dict[str, str] | None:
    """Extract Planning Center EventTime and EventInstance IDs from an iCal UID."""
    match = PLANNING_CENTER_UID_PATTERN.match(clean_text(uid))
    if not match:
        return None
    return match.groupdict()


def planning_center_api_enabled() -> bool:
    return bool(PLANNING_CENTER_APP_ID and PLANNING_CENTER_SECRET)


def planning_center_api_params(window_start: datetime, window_end: datetime) -> dict[str, str]:
    """Build a bounded Calendar API query for public event-instance details."""
    return {
        "include": "event",
        "order": "starts_at",
        "per_page": "100",
        "where[starts_at][gte]": window_start.astimezone(timezone.utc).isoformat(),
        "where[starts_at][lte]": window_end.astimezone(timezone.utc).isoformat(),
        "fields[EventInstance]": ",".join(
            [
                "church_center_url",
                "description",
                "ends_at",
                "image_url",
                "location",
                "name",
                "starts_at",
            ]
        ),
        "fields[Event]": ",".join(
            [
                "description",
                "image_url",
                "name",
                "registration_url",
                "summary",
                "visible_in_church_center",
            ]
        ),
    }


def build_calendar_api_enrichment(
    instances: list[dict],
    included: list[dict],
    target_instance_ids: set[str],
) -> dict[str, dict[str, object]]:
    """Convert JSON:API EventInstance and included Event records into a lookup."""
    event_resources = {
        str(item.get("id")): item
        for item in included
        if item.get("type") == "Event" and item.get("id") is not None
    }
    enrichment: dict[str, dict[str, object]] = {}

    for instance in instances:
        instance_id = str(instance.get("id") or "")
        if not instance_id or instance_id not in target_instance_ids:
            continue

        instance_attributes = instance.get("attributes") or {}
        event_relationship = (
            instance.get("relationships", {}).get("event", {}).get("data") or {}
        )
        event_id = str(event_relationship.get("id") or "")
        event_resource = event_resources.get(event_id, {})
        event_attributes = event_resource.get("attributes") or {}

        enrichment[instance_id] = {
            "planning_center_event_instance_id": instance_id,
            "planning_center_event_id": event_id or None,
            "instance_description": clean_text(instance_attributes.get("description")),
            "instance_image_url": clean_text(instance_attributes.get("image_url")),
            "instance_location": clean_text(instance_attributes.get("location")),
            "church_center_url": clean_text(instance_attributes.get("church_center_url")),
            "event_description": clean_text(event_attributes.get("description")),
            "event_summary": clean_text(event_attributes.get("summary")),
            "event_image_url": clean_text(event_attributes.get("image_url")),
            "registration_url": clean_text(event_attributes.get("registration_url")),
            "visible_in_church_center": event_attributes.get("visible_in_church_center"),
        }

    return enrichment


def fetch_calendar_api_enrichment(
    components: list,
    window_start: datetime,
    window_end: datetime,
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    """
    Fetch Calendar API EventInstance records and their parent Events.

    The iCal feed remains the occurrence source. The API enriches those
    occurrences with the rich public description that Planning Center exposes
    as Event.description, along with public URLs and images.
    """
    target_instance_ids = {
        parsed["event_instance_id"]
        for component in components
        if (parsed := parse_planning_center_uid(clean_text(component.get("UID"))))
    }

    status: dict[str, object] = {
        "enabled": planning_center_api_enabled(),
        "target_instance_count": len(target_instance_ids),
        "matched_instance_count": 0,
        "page_count": 0,
        "api_version": PLANNING_CENTER_API_VERSION,
    }

    if not target_instance_ids:
        return {}, status

    if not planning_center_api_enabled():
        print(
            "Planning Center Calendar API enrichment skipped: "
            "PLANNING_CENTER_APP_ID and PLANNING_CENTER_SECRET are not both set."
        )
        return {}, status

    session = requests.Session()
    session.auth = (PLANNING_CENTER_APP_ID, PLANNING_CENTER_SECRET)
    session.headers.update(
        {
            "Accept": "application/vnd.api+json",
            "User-Agent": (
                "Urbancrest-Knowledge-Event-Sync/1.4.3 "
                "(https://urbancrest.church)"
            ),
            "X-PCO-API-Version": PLANNING_CENTER_API_VERSION,
        }
    )

    url = f"{PLANNING_CENTER_API_BASE}/calendar/v2/event_instances"
    params: dict[str, str] | None = planning_center_api_params(
        window_start, window_end
    )
    instances: list[dict] = []
    included: list[dict] = []

    for page_number in range(1, PLANNING_CENTER_API_MAX_PAGES + 1):
        response = session.get(url, params=params, timeout=45)
        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            body = response.text[:1000]
            raise RuntimeError(
                "Planning Center Calendar API enrichment failed "
                f"with HTTP {response.status_code}: {body}"
            ) from error

        payload = response.json()
        page_data = payload.get("data") or []
        if isinstance(page_data, list):
            instances.extend(item for item in page_data if isinstance(item, dict))
        page_included = payload.get("included") or []
        if isinstance(page_included, list):
            included.extend(item for item in page_included if isinstance(item, dict))

        status["page_count"] = page_number
        next_url = (payload.get("links") or {}).get("next")
        if not next_url:
            break
        url = str(next_url)
        params = None
    else:
        raise RuntimeError(
            "Planning Center Calendar API pagination exceeded "
            f"PLANNING_CENTER_API_MAX_PAGES={PLANNING_CENTER_API_MAX_PAGES}."
        )

    enrichment = build_calendar_api_enrichment(
        instances, included, target_instance_ids
    )
    status["matched_instance_count"] = len(enrichment)
    return enrichment, status


def extract_api_details(api_data: dict[str, object], description: str) -> str:
    """Return rich API details while avoiding a duplicate plain summary."""
    base_values = [
        value
        for value in (
            description,
            clean_text(api_data.get("event_summary")),
        )
        if value
    ]
    normalized_bases = {normalized_content(value) for value in base_values}

    seen: set[str] = set()
    details: list[str] = []
    for raw_candidate in (
        api_data.get("instance_description"),
        api_data.get("event_description"),
    ):
        candidate = clean_text(raw_candidate)
        if not candidate:
            continue

        normalized_candidate = normalized_content(candidate)
        if not normalized_candidate or normalized_candidate in normalized_bases:
            continue

        for base in base_values:
            if candidate.startswith(base):
                candidate = candidate[len(base):].lstrip(" \t\r\n:-")
                normalized_candidate = normalized_content(candidate)
                break

        if (
            not normalized_candidate
            or normalized_candidate in normalized_bases
            or normalized_candidate in seen
        ):
            continue

        seen.add(normalized_candidate)
        details.append(candidate)

    return "\n\n".join(details).strip()


def load_yaml(path: Path, fallback: dict) -> dict:
    if not path.exists():
        return fallback
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    return parsed if isinstance(parsed, dict) else fallback


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


def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def stable_event_id(uid: str, recurrence_id: str, start: datetime) -> str:
    return stable_id("event", f"{uid}|{recurrence_id}|{start.isoformat()}")


def normalize_group_series_text(value: str) -> str:
    """Normalize a group title or location for recurring-series matching."""
    normalized = normalize_for_matching(clean_text(value))
    normalized = re.sub(r"\\s+", " ", normalized).strip()
    return normalized


def stable_series_id(
    title: str,
    location: str,
    series_key: str | None = None,
) -> str:
    """
    Build a recurring Small Group series ID.

    Planning Center may assign a different iCal UID to every occurrence, so UID
    is intentionally not part of the automatic grouping key. By default, group
    occurrences are consolidated by normalized title and normalized location.

    A manual series_key override may be used when two distinct groups share the
    same title and location, or when one group's location changes.
    """
    if series_key:
        source = f"override|{normalize_group_series_text(series_key)}"
    else:
        normalized_title = normalize_group_series_text(title)
        normalized_location = normalize_group_series_text(location)
        source = f"title|{normalized_title}|location|{normalized_location}"

    return stable_id("group", source)


def slugify(value: str, max_length: int = 72) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_text).strip("-").lower()
    slug = re.sub(r"-{2,}", "-", slug)
    return slug[:max_length].rstrip("-") or "item"


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


def public_calendar_info_url(
    info_url: str | None,
    api_data: dict[str, object],
) -> str | None:
    """Return only public-safe event information URLs.

    Church Center calendar-instance URLs are only trustworthy when the parent
    Planning Center event is explicitly visible in Church Center. Registration
    URLs are handled separately and are not affected by this policy.
    """
    candidate = clean_text(info_url) or clean_text(api_data.get("church_center_url"))
    if not candidate:
        return None

    if "churchcenter.com/calendar/event/" in candidate.casefold():
        if api_data.get("visible_in_church_center") is not True:
            return None

    return candidate


def extract_image(component, *text_fields: str) -> str | None:
    candidates: list[str] = []

    for key in ("ATTACH", "IMAGE"):
        raw = component.get(key)
        if raw:
            values = raw if isinstance(raw, list) else [raw]
            candidates.extend(str(value) for value in values)

    candidates.extend(
        extract_urls(*text_fields, clean_text(component.get("X-ALT-DESC")))
    )

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


def infer_category(
    title: str,
    description: str,
    ministries: list[str],
    category_config: dict,
) -> tuple[str, int, str]:
    haystack = normalize_for_matching(f"{title}\n{description}")
    categories = category_config.get("categories", {})
    order = category_config.get("classification_order", [])

    for category_name in order:
        category = categories.get(category_name, {})
        terms = category.get("terms", [])
        if any(normalize_for_matching(str(term)) in haystack for term in terms):
            return (
                category_name,
                int(category.get("priority", 50)),
                str(category.get("collection", "main_events")),
            )

    fallback_name = (
        "ministry_event"
        if any(ministry != "churchwide" for ministry in ministries)
        else "general_event"
    )
    fallback = categories.get(fallback_name, {})
    return (
        fallback_name,
        int(fallback.get("priority", 50)),
        str(fallback.get("collection", "main_events")),
    )


def title_rule_matches(rule: dict, title: str) -> bool:
    normalized_title = normalize_for_matching(title)

    if "title_equals" in rule:
        return normalized_title == normalize_for_matching(str(rule["title_equals"]))

    if "title_contains" in rule:
        return normalize_for_matching(str(rule["title_contains"])) in normalized_title

    if "title_regex" in rule:
        return bool(re.search(str(rule["title_regex"]), title, flags=re.IGNORECASE))

    return False


def apply_override(event: dict[str, object], overrides: dict) -> None:
    merged: dict = {}

    uid_overrides = overrides.get("uid_overrides", {})
    uid_rule = uid_overrides.get(str(event["uid"]))
    if isinstance(uid_rule, dict):
        merged.update(uid_rule)

    for rule in overrides.get("title_rules", []):
        if isinstance(rule, dict) and title_rule_matches(rule, str(event["title"])):
            merged.update(rule)

    if "event_category" in merged:
        event["event_category"] = str(merged["event_category"])
    if "event_priority" in merged:
        event["event_priority"] = int(merged["event_priority"])
    if "collection" in merged:
        event["collection"] = str(merged["collection"])
    if "ministries" in merged:
        event["ministries"] = list(merged["ministries"])
    if "audiences" in merged:
        event["audiences"] = list(merged["audiences"])
    if "location" in merged:
        event["location"] = str(merged["location"])
    if "series_key" in merged:
        event["series_key"] = str(merged["series_key"])


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
    return "[" + ", ".join(yaml_quote(str(value)) for value in values) + "]"


def select_main_events(events: list[dict[str, object]]) -> list[dict[str, object]]:
    protected = [
        event for event in events if int(event["event_priority"]) >= 80
    ]
    lower_priority = [
        event for event in events if int(event["event_priority"]) < 80
    ]

    protected.sort(
        key=lambda event: (
            event["_start_dt"],
            str(event["title"]).casefold(),
        )
    )

    if len(protected) >= MAX_MAIN_EVENTS:
        selected = protected[:MAX_MAIN_EVENTS]
        print(
            "Warning: high-priority events exceeded EVENT_MAX_MAIN_EVENTS.",
            file=sys.stderr,
        )
    else:
        remaining = MAX_MAIN_EVENTS - len(protected)
        lower_priority.sort(
            key=lambda event: (
                -int(event["event_priority"]),
                event["_start_dt"],
                str(event["title"]).casefold(),
            )
        )
        selected = protected + lower_priority[:remaining]

    selected.sort(
        key=lambda event: (
            event["_start_dt"],
            -int(event["event_priority"]),
            str(event["title"]).casefold(),
        )
    )
    return selected


def annotate_chronology(events: list[dict[str, object]]) -> None:
    seen_ministries: set[str] = set()
    seen_audiences: set[str] = set()

    for rank, event in enumerate(events, start=1):
        event["chronological_rank"] = rank
        event["next_for_ministries"] = []
        event["next_for_audiences"] = []

        for ministry in event["ministries"]:
            ministry_name = str(ministry)
            if ministry_name != "churchwide" and ministry_name not in seen_ministries:
                event["next_for_ministries"].append(ministry_name)
                seen_ministries.add(ministry_name)

        for audience in event["audiences"]:
            audience_name = str(audience)
            if audience_name != "everyone" and audience_name not in seen_audiences:
                event["next_for_audiences"].append(audience_name)
                seen_audiences.add(audience_name)


def write_event_article(event: dict[str, object], generated_at: str) -> str:
    start: datetime = event["_start_dt"]
    title = str(event["title"])
    slug = (
        f"{start.strftime('%Y-%m-%d')}-"
        f"{slugify(title)}-{str(event['id'])[-6:]}"
    )
    relative_path = f"knowledge/events/generated/{slug}.md"
    path = ROOT / relative_path

    tags = ["event", "calendar", "upcoming", str(event["event_category"])]
    tags.extend(str(value) for value in event["ministries"])
    tags.extend(str(value) for value in event["audiences"])
    tags = list(dict.fromkeys(tags))

    lines = [
        "---",
        f"id: events.live.{event['id']}",
        "version: 1.4.3",
        "status: published",
        f"priority: {event['event_priority']}",
        f"title: {yaml_quote(title)}",
        f"summary: {yaml_quote(str(event['summary']))}",
        "category: [events]",
        f"event_category: {yaml_quote(str(event['event_category']))}",
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
        f"  - {yaml_quote('What are the details for ' + title + '?')}",
        f"  - {yaml_quote('What is the menu for ' + title + '?')}",
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

    for field in (
        "registration_url",
        "info_url",
        "image_url",
        "location",
        "details_source",
        "planning_center_event_id",
        "planning_center_event_instance_id",
        "planning_center_event_time_id",
    ):
        if event.get(field):
            lines.append(f"{field}: {yaml_quote(str(event[field]))}")

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
    if event.get("details"):
        lines.extend(["## Details", "", str(event["details"]), ""])
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


def collapse_small_groups(
    occurrences: list[dict[str, object]]
) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)

    for occurrence in occurrences:
        series_id = stable_series_id(
            title=str(occurrence["title"]),
            location=str(occurrence.get("location") or ""),
            series_key=(
                str(occurrence["series_key"])
                if occurrence.get("series_key")
                else None
            ),
        )
        grouped[series_id].append(occurrence)

    groups: list[dict[str, object]] = []

    for series_id, meetings in grouped.items():
        meetings.sort(key=lambda meeting: meeting["_start_dt"])
        first = meetings[0]
        limited = meetings[:MAX_SMALL_GROUP_OCCURRENCES]

        future_meetings = [
            {
                "start": meeting["start"],
                "end": meeting["end"],
                "sort_start_utc": meeting["sort_start_utc"],
                "sort_end_utc": meeting["sort_end_utc"],
                "display_when": meeting["display_when"],
                "all_day": meeting["all_day"],
            }
            for meeting in limited
        ]

        source_uids = list(dict.fromkeys(str(meeting["uid"]) for meeting in meetings))

        groups.append({
            "id": series_id,
            "source_uids": source_uids,
            "title": first["title"],
            "summary": first["summary"],
            "description": first.get("description"),
            "details": first.get("details"),
            "details_source": first.get("details_source"),
            "planning_center_event_id": first.get("planning_center_event_id"),
            "planning_center_event_instance_id": first.get("planning_center_event_instance_id"),
            "planning_center_event_time_id": first.get("planning_center_event_time_id"),
            "location": first.get("location"),
            "registration_url": first.get("registration_url"),
            "info_url": first.get("info_url"),
            "image_url": first.get("image_url"),
            "ministries": first["ministries"],
            "audiences": first["audiences"],
            "event_category": "small_group_meeting",
            "event_priority": first["event_priority"],
            "next_meeting": future_meetings[0],
            "future_meetings": future_meetings,
            "meeting_count_in_window": len(meetings),
            "_start_dt": first["_start_dt"],
        })

    groups.sort(key=lambda group: (group["_start_dt"], str(group["title"]).casefold()))
    return groups[:MAX_SMALL_GROUP_SERIES]


def write_group_article(group: dict[str, object], generated_at: str) -> str:
    title = str(group["title"])
    slug = f"{slugify(title)}-{str(group['id'])[-6:]}"
    relative_path = f"knowledge/small-groups/generated/{slug}.md"
    path = ROOT / relative_path

    tags = ["small_group", "recurring", "calendar"]
    tags.extend(str(value) for value in group["audiences"])
    tags = list(dict.fromkeys(tags))

    next_meeting = group["next_meeting"]

    lines = [
        "---",
        f"id: small_groups.live.{group['id']}",
        "version: 1.4.3",
        "status: published",
        f"priority: {group['event_priority']}",
        f"title: {yaml_quote(title)}",
        f"summary: {yaml_quote(str(group['summary']))}",
        "category: [small_groups]",
        "event_category: small_group_meeting",
        "intent:",
        "  primary: small_group_details",
        "  secondary: [next_small_group_meeting, small_groups, calendar]",
        "audience: " + yaml_inline_list(group["audiences"]),
        "ministries: " + yaml_inline_list(group["ministries"]),
        "answer_style: helpful",
        "confidence: high",
        "tags: " + yaml_inline_list(tags),
        "search_terms:",
        f"  - {yaml_quote(title)}",
        f"  - {yaml_quote('Tell me about ' + title)}",
        f"  - {yaml_quote('What are the details for ' + title + '?')}",
        f"series_id: {group['id']}",
        f"next_meeting_start: {yaml_quote(str(next_meeting['start']))}",
        f"next_meeting_end: {yaml_quote(str(next_meeting['end']))}",
        f"sort_start_utc: {yaml_quote(str(next_meeting['sort_start_utc']))}",
        f"sort_end_utc: {yaml_quote(str(next_meeting['sort_end_utc']))}",
        f"meeting_count_in_window: {group['meeting_count_in_window']}",
    ]

    for field in (
        "registration_url",
        "info_url",
        "image_url",
        "location",
        "details_source",
        "planning_center_event_id",
        "planning_center_event_instance_id",
        "planning_center_event_time_id",
    ):
        if group.get(field):
            lines.append(f"{field}: {yaml_quote(str(group[field]))}")

    lines.extend([
        f"last_generated: {generated_at}",
        "---",
        "",
        f"# {title}",
        "",
        str(group["summary"]),
        "",
        f"**Next meeting:** {next_meeting['display_when']}",
        "",
    ])

    if group.get("location"):
        lines.extend([f"**Where:** {group['location']}", ""])
    if group.get("description"):
        lines.extend([str(group["description"]), ""])
    if group.get("details"):
        lines.extend(["## Details", "", str(group["details"]), ""])
    if group.get("registration_url"):
        lines.extend([f"**Registration:** {group['registration_url']}", ""])
    elif group.get("info_url"):
        lines.extend([f"**More information:** {group['info_url']}", ""])

    if len(group["future_meetings"]) > 1:
        lines.extend(["## Upcoming meetings", ""])
        for meeting in group["future_meetings"]:
            lines.append(f"- {meeting['display_when']}")
        lines.append("")

    lines.extend([
        "This small group schedule is synchronized automatically from Urbancrest's live calendar.",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
    return relative_path


def write_event_index(events: list[dict[str, object]], generated_at: str) -> None:
    lines = [
        "---",
        "id: events.upcoming.live",
        "version: 1.4.3",
        "status: published",
        "priority: 100",
        "title: Upcoming Events",
        "summary: Major, ministry, churchwide, and general events synchronized from the Urbancrest calendar.",
        "category: [events]",
        "intent:",
        "  primary: upcoming_events",
        "  secondary: [calendar, schedule, whats_happening, next_ministry_event]",
        "audience: [everyone]",
        "answer_style: helpful",
        "confidence: high",
        "tags: [events, calendar, upcoming, schedule]",
        "resources:",
        "  - events.live",
        "calendar_sort_order: sort_start_utc_ascending",
        f"last_generated: {generated_at}",
        "---",
        "",
        "# Upcoming Events",
        "",
        "This index excludes routine Small Group meetings, which are stored separately.",
        "Events are listed in ascending chronological order.",
        "",
    ]

    if not events:
        lines.extend(["There are currently no upcoming events listed.", ""])
    else:
        for event in events:
            lines.extend([
                f"## {event['title']}",
                "",
                f"**Category:** {str(event['event_category']).replace('_', ' ').title()}",
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

    EVENT_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVENT_INDEX_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_group_index(groups: list[dict[str, object]], generated_at: str) -> None:
    lines = [
        "---",
        "id: small_groups.upcoming.live",
        "version: 1.4.3",
        "status: published",
        "priority: 70",
        "title: Upcoming Small Groups",
        "summary: Recurring Small Group schedules synchronized from the Urbancrest calendar.",
        "category: [small_groups]",
        "intent:",
        "  primary: small_groups",
        "  secondary: [next_small_group_meeting, group_schedule, calendar]",
        "audience: [everyone]",
        "answer_style: helpful",
        "confidence: high",
        "tags: [small_groups, groups, calendar, recurring]",
        "resources:",
        "  - small_groups.live",
        "calendar_sort_order: sort_start_utc_ascending",
        f"last_generated: {generated_at}",
        "---",
        "",
        "# Upcoming Small Groups",
        "",
        "Each recurring Small Group appears once with its next meeting and future schedule.",
        "",
    ]

    if not groups:
        lines.extend(["There are currently no Small Group meetings listed.", ""])
    else:
        for group in groups:
            next_meeting = group["next_meeting"]
            lines.extend([
                f"## {group['title']}",
                "",
                f"**Next meeting:** {next_meeting['display_when']}",
                "",
            ])
            if group.get("location"):
                lines.extend([f"**Where:** {group['location']}", ""])
            lines.extend([f"Detailed group file: `{group['knowledge_file']}`", ""])

    GROUP_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    GROUP_INDEX_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    feed_url = os.getenv("ICAL_FEED_URL", "").strip()
    if not feed_url:
        print("ICAL_FEED_URL is not set.", file=sys.stderr)
        return 1

    if feed_url.startswith("webcal://"):
        feed_url = "https://" + feed_url[len("webcal://"):]

    category_config = load_yaml(CATEGORY_RULES_PATH, {"categories": {}})
    overrides = load_yaml(OVERRIDES_PATH, {})

    response = requests.get(
        feed_url,
        timeout=30,
        headers={"User-Agent": "Urbancrest-Knowledge-Event-Sync/1.4.3"},
    )
    response.raise_for_status()

    calendar = Calendar.from_ical(response.content)
    now = datetime.now(TIMEZONE)
    window_start = now - timedelta(days=1)
    window_end = now + timedelta(days=LOOKAHEAD_DAYS)

    components = list(
        recurring_ical_events.of(calendar).between(window_start, window_end)
    )
    api_enrichment, api_status = fetch_calendar_api_enrichment(
        components, window_start, window_end
    )
    parsed_events: list[dict[str, object]] = []

    for component in components:
        status = clean_text(component.get("STATUS", "CONFIRMED")).upper()
        if status == "CANCELLED":
            continue

        title = clean_text(component.get("SUMMARY")) or "Untitled Event"
        uid = clean_text(component.get("UID")) or title
        planning_center_ids = parse_planning_center_uid(uid) or {}
        event_instance_id = planning_center_ids.get("event_instance_id", "")
        api_data = api_enrichment.get(event_instance_id, {})

        description = (
            clean_text(component.get("DESCRIPTION"))
            or clean_text(api_data.get("event_summary"))
        )
        ical_details = extract_details(component, description)
        api_details = extract_api_details(api_data, description)
        details = ical_details or api_details
        details_source = (
            "planning_center_ical"
            if ical_details
            else "planning_center_calendar_api"
            if api_details
            else None
        )
        public_text = "\n\n".join(
            value for value in (description, details) if value
        )
        location = normalize_location(
            clean_text(component.get("LOCATION"))
            or clean_text(api_data.get("instance_location"))
        )
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

        urls = extract_urls(
            clean_text(component.get("URL")),
            description,
            details,
            clean_text(component.get("X-ALT-DESC")),
            clean_text(api_data.get("event_description")),
            clean_text(api_data.get("event_summary")),
        )
        registration_url, info_url = classify_urls(urls)
        registration_url = (
            clean_text(api_data.get("registration_url")) or registration_url
        )
        info_url = public_calendar_info_url(info_url, api_data)
        image_url = (
            extract_image(component, description, details)
            or clean_text(api_data.get("instance_image_url"))
            or clean_text(api_data.get("event_image_url"))
            or None
        )
        ministries, audiences = infer_labels(title, public_text)
        event_category, event_priority, collection = infer_category(
            title, public_text, ministries, category_config
        )
        when = display_when(start, end, all_day)
        summary = make_summary(title, when, location, description or details)

        event = {
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
            "details": details or None,
            "details_source": details_source,
            "planning_center_event_id": api_data.get("planning_center_event_id"),
            "planning_center_event_instance_id": (
                event_instance_id or None
            ),
            "planning_center_event_time_id": (
                planning_center_ids.get("event_time_id") or None
            ),
            "registration_url": registration_url,
            "info_url": info_url,
            "publicly_listed": (
                api_data.get("visible_in_church_center")
                if isinstance(api_data.get("visible_in_church_center"), bool)
                else None
            ),
            "image_url": image_url,
            "ministries": ministries,
            "audiences": audiences,
            "event_category": event_category,
            "event_priority": event_priority,
            "collection": collection,
            "status": status.lower(),
            "_start_dt": start,
            "_end_dt": end,
            "_api_enriched": bool(api_data),
            "_api_details_imported": bool(api_details),
        }

        apply_override(event, overrides)

        if event["collection"] != "exclude":
            parsed_events.append(event)

    main_candidates = [
        event for event in parsed_events if event["collection"] == "main_events"
    ]
    small_group_occurrences = [
        event for event in parsed_events if event["collection"] == "small_groups"
    ]

    main_events = select_main_events(main_candidates)
    annotate_chronology(main_events)
    small_groups = collapse_small_groups(small_group_occurrences)

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    for directory in (EVENT_GENERATED_DIR, GROUP_GENERATED_DIR):
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)

    for event in main_events:
        event["knowledge_file"] = write_event_article(event, generated_at)

    for group in small_groups:
        group["knowledge_file"] = write_group_article(group, generated_at)

    event_registry = {
        "version": "1.4.3",
        "generated_at": generated_at,
        "timezone": TIMEZONE_NAME,
        "source": (
            "planning_center_ical+calendar_api"
            if api_status.get("enabled")
            else "planning_center_ical"
        ),
        "api_enrichment": api_status,
        "source_of_truth_for_calendar_intents": True,
        "collection": "main_events",
        "excluded_collection": "small_groups-live.yaml",
        "sort_order": "sort_start_utc_ascending",
        "lookahead_days": LOOKAHEAD_DAYS,
        "selection": {
            "max_events": MAX_MAIN_EVENTS,
            "protected_priority_minimum": 80,
            "policy": "Protect all major and ministry events before lower-priority events.",
        },
        "event_count": len(main_events),
        "events": [
            {
                key: value
                for key, value in event.items()
                if not key.startswith("_") and value is not None
            }
            for event in main_events
        ],
    }

    group_registry = {
        "version": "1.4.3",
        "generated_at": generated_at,
        "timezone": TIMEZONE_NAME,
        "source": (
            "planning_center_ical+calendar_api"
            if api_status.get("enabled")
            else "planning_center_ical"
        ),
        "api_enrichment": api_status,
        "source_of_truth_for_small_group_intents": True,
        "collection": "small_groups",
        "sort_order": "next_meeting.sort_start_utc_ascending",
        "lookahead_days": LOOKAHEAD_DAYS,
        "max_series": MAX_SMALL_GROUP_SERIES,
        "max_occurrences_per_series": MAX_SMALL_GROUP_OCCURRENCES,
        "group_count": len(small_groups),
        "source_occurrence_count": len(small_group_occurrences),
        "groups": [
            {
                key: value
                for key, value in group.items()
                if not key.startswith("_") and value is not None
            }
            for group in small_groups
        ],
    }

    EVENT_REGISTRY_PATH.write_text(
        yaml.safe_dump(event_registry, sort_keys=False, allow_unicode=True, width=1000),
        encoding="utf-8",
    )
    GROUP_REGISTRY_PATH.write_text(
        yaml.safe_dump(group_registry, sort_keys=False, allow_unicode=True, width=1000),
        encoding="utf-8",
    )

    write_event_index(main_events, generated_at)
    write_group_index(small_groups, generated_at)

    details_count = sum(1 for event in parsed_events if event.get("details"))
    api_enriched_count = sum(
        1 for event in parsed_events if event.get("_api_enriched")
    )
    api_details_count = sum(
        1 for event in parsed_events if event.get("_api_details_imported")
    )
    print(f"Parsed {len(parsed_events)} future event occurrences.")
    print(
        "Calendar API enrichment matched "
        f"{api_enriched_count} parsed event occurrences; "
        f"imported rich details for {api_details_count}."
    )
    print(f"Imported separate details for {details_count} event occurrences total.")
    print(
        f"Wrote {len(main_events)} main events "
        f"from {len(main_candidates)} main-event candidates."
    )
    duplicate_occurrence_count = len(small_group_occurrences) - len(small_groups)
    print(
        f"Collapsed {len(small_group_occurrences)} Small Group occurrences "
        f"into {len(small_groups)} Small Group series "
        f"({duplicate_occurrence_count} recurring occurrences consolidated)."
    )
    print("Main calendar sort order: sort_start_utc ascending.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
