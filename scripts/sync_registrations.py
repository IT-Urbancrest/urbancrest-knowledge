#!/usr/bin/env python3
"""Merge future public Planning Center Registrations signups into events-live.yaml.

This script intentionally runs *after* scripts/sync_events.py. The existing iCal +
Calendar API sync remains the canonical occurrence source for calendar events. This
step supplements it with future Registrations signups that may appear on the public
Events page but not on the calendar feed, and enriches matching calendar records
with registration details/status.

Required environment variables:
  PLANNING_CENTER_APP_ID
  PLANNING_CENTER_SECRET

Optional:
  PLANNING_CENTER_REGISTRATIONS_API_VERSION (default: 2025-05-01)
  PLANNING_CENTER_API_BASE (default: https://api.planningcenteronline.com)
  EVENT_LOOKAHEAD_DAYS (default: 365)
  EVENT_MAX_MAIN_EVENTS (default: 150)
  REGISTRATIONS_CATEGORY_ALLOWLIST (comma-separated; blank = all categories)
  REGISTRATIONS_CATEGORY_DENYLIST (comma-separated; blank = none)

Version 1.5.4 keeps the relationship-linkage fix from 1.5.3 and removes the
assumption that a specific Planning Center category determines public website
eligibility. Category filtering remains optional and is blank by default.
"""

from __future__ import annotations

import hashlib
import html
import os
from collections import Counter
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
EVENT_REGISTRY_PATH = ROOT / "registry" / "events-live.yaml"
EVENT_INDEX_PATH = ROOT / "knowledge" / "events" / "upcoming-events.md"

TIMEZONE_NAME = os.getenv("EVENT_TIMEZONE", "America/New_York")
TIMEZONE = ZoneInfo(TIMEZONE_NAME)
LOOKAHEAD_DAYS = int(os.getenv("EVENT_LOOKAHEAD_DAYS", "365"))
MAX_MAIN_EVENTS = int(os.getenv("EVENT_MAX_MAIN_EVENTS", "150"))
API_BASE = os.getenv("PLANNING_CENTER_API_BASE", "https://api.planningcenteronline.com").rstrip("/")
API_VERSION = os.getenv("PLANNING_CENTER_REGISTRATIONS_API_VERSION", "2025-05-01")
API_MAX_PAGES = int(os.getenv("PLANNING_CENTER_API_MAX_PAGES", "50"))


def env_csv(name: str) -> set[str]:
    return {
        item.strip().casefold()
        for item in os.getenv(name, "").split(",")
        if item.strip()
    }


CATEGORY_ALLOWLIST = env_csv("REGISTRATIONS_CATEGORY_ALLOWLIST")
CATEGORY_DENYLIST = env_csv("REGISTRATIONS_CATEGORY_DENYLIST")


def clean_text(value: Any) -> str:
    """Convert lightweight HTML-ish Planning Center descriptions to search text."""
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = text.replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_text(value: Any) -> str:
    text = clean_text(value).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
        host = parts.netloc.casefold()
        path = re.sub(r"/+", "/", parts.path).rstrip("/")
        # Query parameters on Church Center registration links are not identity.
        return urlunsplit((parts.scheme.casefold(), host, path, "", ""))
    except Exception:
        return raw.rstrip("/").casefold()


def parse_dt(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TIMEZONE)
        return dt
    except ValueError:
        return None


def iso_value(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def utc_sort_value(dt: datetime | None) -> str | None:
    if not dt:
        return None
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def local_date_key(value: Any) -> str:
    dt = parse_dt(value)
    return dt.astimezone(TIMEZONE).date().isoformat() if dt else ""


def display_when(start: datetime | None, end: datetime | None, all_day: bool) -> str:
    if not start:
        return ""
    local_start = start.astimezone(TIMEZONE)
    local_end = end.astimezone(TIMEZONE) if end else None
    if all_day:
        return local_start.strftime("%A, %B %-d, %Y")
    if local_end and local_end.date() == local_start.date():
        return f"{local_start.strftime('%A, %B %-d, %Y at %-I:%M %p')} - {local_end.strftime('%-I:%M %p')}"
    return local_start.strftime("%A, %B %-d, %Y at %-I:%M %p")


def short_summary(description: str, limit: int = 280) -> str:
    text = re.sub(r"\s+", " ", description).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3].rsplit(" ", 1)[0].rstrip() + "..."


def stable_registration_event_id(signup_id: str, signup_time_id: str, start: datetime | None) -> str:
    seed = f"registrations:{signup_id}:{signup_time_id}:{utc_sort_value(start) or ''}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
    return f"pc-registration-{signup_id}-{digest}"


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def infer_labels(title: str, categories: list[str], description: str) -> tuple[list[str], list[str], str, int]:
    """Lightweight fallback classification for Registrations-only events.

    Calendar-backed events keep their existing classification during a merge. This
    function only supplies compatible metadata for events that exist exclusively in
    Registrations.
    """
    haystack = normalize_text(" ".join([title, *categories, description]))
    ministries: list[str] = []
    audiences: list[str] = []
    category = "general_event"
    priority = 65

    rules = [
        (r"\b(women|womens|women s|ladies)\b", "women", "women", "womens_event"),
        (r"\b(men|mens|men s)\b", "men", "men", "mens_event"),
        (r"\b(student|students|youth|teen|teens)\b", "students", "students", "student_event"),
        (r"\b(kid|kids|children|child|awana|vbs)\b", "kids", "children", "kids_event"),
        (r"\b(preschool)\b", "kids", "children", "kids_event"),
        (r"\b(nursery)\b", "kids", "children", "kids_event"),
        (r"\b(senior|seniors|legacy builders)\b", "senior", "seniors", "senior_event"),
        (r"\b(worship|choir|music)\b", "worship", "all", "worship_event"),
        (r"\b(local mission|local missions|community outreach|outreach|serve lebanon)\b", "local_missions", "all", "local_missions_event"),
        (r"\b(mission|missions|mission trip)\b", "missions", "all", "missions_event"),
        (r"\b(family|families)\b", "family", "families", "family_event"),
        (r"\b(volunteer|serve|serving)\b", "volunteer", "all", "serving_event"),
    ]
    for pattern, ministry, audience, inferred_category in rules:
        if re.search(pattern, haystack):
            ministries.append(ministry)
            audiences.append(audience)
            if category == "general_event":
                category = inferred_category

    if re.search(r"\b(conference|summit|retreat)\b", haystack):
        priority = 85
    elif re.search(r"\b(class|engage|membership|new member)\b", haystack):
        priority = 75
    elif categories:
        priority = 70

    priority = max(priority, 80)
    return unique(ministries), unique(audiences), category, priority


def category_allowed(categories: list[str]) -> bool:
    normalized = {item.casefold() for item in categories}
    if CATEGORY_DENYLIST and normalized.intersection(CATEGORY_DENYLIST):
        return False
    if CATEGORY_ALLOWLIST and not normalized.intersection(CATEGORY_ALLOWLIST):
        return False
    return True


def fetch_signups() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    app_id = os.getenv("PLANNING_CENTER_APP_ID", "").strip()
    secret = os.getenv("PLANNING_CENTER_SECRET", "").strip()
    if not app_id or not secret:
        raise RuntimeError("PLANNING_CENTER_APP_ID and PLANNING_CENTER_SECRET are required")

    url = f"{API_BASE}/registrations/v2/signups"
    params: dict[str, str] | None = {
        "filter": "unarchived",
        "include": "next_signup_time,signup_times,signup_location,categories,selection_types",
        "per_page": "100",
        "fields[SignupTime]": "all_day,ends_at,starts_at,updated_at",
        "fields[SignupLocation]": "formatted_address,full_formatted_address,latitude,longitude,location_type,name,subpremise,url",
        "fields[Category]": "name",
        "fields[SelectionType]": "at_maximum_capacity,available_capacity,maximum_capacity,name,price_cents,price_currency,price_currency_symbol,price_formatted,publicly_available,waitlist",
    }
    headers = {
        "Accept": "application/vnd.api+json",
        "X-PCO-API-Version": API_VERSION,
        "User-Agent": "urbancrest-knowledge-registrations-sync",
    }

    signups: list[dict[str, Any]] = []
    included: dict[tuple[str, str], dict[str, Any]] = {}
    page_count = 0

    while url:
        page_count += 1
        if page_count > API_MAX_PAGES:
            raise RuntimeError(
                f"Planning Center Registrations pagination exceeded PLANNING_CENTER_API_MAX_PAGES={API_MAX_PAGES}."
            )
        response = requests.get(
            url,
            params=params,
            headers=headers,
            auth=(app_id, secret),
            timeout=30,
        )
        if not response.ok:
            body = clean_text(response.text)[:600]
            raise RuntimeError(f"Registrations API request failed ({response.status_code}): {body}")
        payload = response.json()
        signups.extend(payload.get("data") or [])
        for item in payload.get("included") or []:
            item_type = str(item.get("type") or "")
            item_id = str(item.get("id") or "")
            if item_type and item_id:
                included[(item_type, item_id)] = item
        next_url = (payload.get("links") or {}).get("next")
        url = str(next_url).strip() if next_url else ""
        params = None  # Planning Center's next URL already carries pagination params.

    return signups, {"included": included, "page_count": page_count}


def relationship_linkage_counts(signups: list[dict[str, Any]]) -> dict[str, int]:
    """Count primary Signup relationship linkage returned by Planning Center.

    These counts are aggregate-only so the public registry can diagnose API shape
    changes without exposing internal signup names.
    """
    names = (
        "next_signup_time",
        "signup_times",
        "signup_location",
        "categories",
        "selection_types",
    )
    counts: dict[str, int] = {}
    for name in names:
        present = 0
        linked = 0
        for signup in signups:
            relationships = signup.get("relationships") or {}
            if name not in relationships:
                continue
            present += 1
            data = (relationships.get(name) or {}).get("data")
            if isinstance(data, dict):
                if data.get("id") and data.get("type"):
                    linked += 1
            elif isinstance(data, list):
                if any(
                    isinstance(item, dict) and item.get("id") and item.get("type")
                    for item in data
                ):
                    linked += 1
        counts[f"{name}_relationship_present"] = present
        counts[f"{name}_with_linkage"] = linked
    return counts


def related_resource(
    signup: dict[str, Any],
    relationship_name: str,
    included: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any] | None:
    rel = ((signup.get("relationships") or {}).get(relationship_name) or {}).get("data")
    if not isinstance(rel, dict):
        return None
    key = (str(rel.get("type") or ""), str(rel.get("id") or ""))
    return included.get(key)


def related_resources(
    signup: dict[str, Any],
    relationship_name: str,
    included: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    rel = ((signup.get("relationships") or {}).get(relationship_name) or {}).get("data")
    if not isinstance(rel, list):
        return []
    result = []
    for item in rel:
        if not isinstance(item, dict):
            continue
        key = (str(item.get("type") or ""), str(item.get("id") or ""))
        resource = included.get(key)
        if resource:
            result.append(resource)
    return result


def choose_signup_time(
    signup: dict[str, Any],
    included: dict[tuple[str, str], dict[str, Any]],
    now: datetime,
    cutoff: datetime,
) -> dict[str, Any] | None:
    """Choose the earliest current/future signup time within the lookahead window.

    ``next_signup_time`` is Planning Center's convenient primary relationship, but
    some otherwise-public signups may not expose it consistently. Include the full
    ``signup_times`` relationship as a fallback and select deterministically.
    """
    resources: list[dict[str, Any]] = []
    primary = related_resource(signup, "next_signup_time", included)
    if primary:
        resources.append(primary)
    resources.extend(related_resources(signup, "signup_times", included))

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for resource in resources:
        key = (str(resource.get("type") or ""), str(resource.get("id") or ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(resource)

    candidates: list[tuple[datetime, dict[str, Any]]] = []
    now_utc = now.astimezone(timezone.utc)
    cutoff_utc = cutoff.astimezone(timezone.utc)
    for resource in deduped:
        attrs = resource.get("attributes") or {}
        start = parse_dt(attrs.get("starts_at"))
        end = parse_dt(attrs.get("ends_at")) or start
        if not start:
            continue
        if (end or start).astimezone(timezone.utc) < now_utc:
            continue
        if start.astimezone(timezone.utc) > cutoff_utc:
            continue
        candidates.append((start.astimezone(timezone.utc), resource))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], str(item[1].get("id") or "")))
    return candidates[0][1]


def format_location(resource: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    if not resource:
        return "", {}
    attrs = resource.get("attributes") or {}
    name = clean_text(attrs.get("name"))
    address = clean_text(attrs.get("full_formatted_address") or attrs.get("formatted_address"))
    if name and address and normalize_text(name) not in normalize_text(address):
        display = f"{name} - {address}"
    else:
        display = name or address
    structured = {
        "name": name or None,
        "address": address or None,
        "latitude": attrs.get("latitude"),
        "longitude": attrs.get("longitude"),
        "url": attrs.get("url"),
    }
    return display, {key: value for key, value in structured.items() if value not in (None, "")}


def signup_to_event(
    signup: dict[str, Any],
    included: dict[tuple[str, str], dict[str, Any]],
    now: datetime,
    cutoff: datetime,
    diagnostics: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    def skip(reason: str) -> None:
        if diagnostics is not None:
            diagnostics["skip_reason"] = reason
        return None

    attrs = signup.get("attributes") or {}
    if attrs.get("archived") is True:
        return skip("archived")

    signup_id = str(signup.get("id") or "").strip()
    title = clean_text(attrs.get("name"))
    registration_url = str(attrs.get("new_registration_url") or "").strip()
    if not signup_id or not title or not registration_url:
        # A public event-page registration should have a stable public signup URL.
        return skip("missing_id_title_or_public_registration_url")

    time_resource = choose_signup_time(signup, included, now, cutoff)
    if not time_resource:
        return skip("no_current_or_future_signup_time_within_lookahead")
    time_attrs = time_resource.get("attributes") or {}
    start = parse_dt(time_attrs.get("starts_at"))
    end = parse_dt(time_attrs.get("ends_at")) or start
    if not start:
        return skip("signup_time_missing_start")
    effective_end = end or start
    if effective_end.astimezone(timezone.utc) < now.astimezone(timezone.utc):
        return skip("signup_time_past")
    if start.astimezone(timezone.utc) > cutoff.astimezone(timezone.utc):
        return skip("signup_time_beyond_lookahead")

    categories = unique(
        [
            clean_text((resource.get("attributes") or {}).get("name"))
            for resource in related_resources(signup, "categories", included)
        ]
    )
    if not category_allowed(categories):
        return skip("category_filtered")

    registration_options: list[dict[str, Any]] = []
    for resource in related_resources(signup, "selection_types", included):
        option_attrs = resource.get("attributes") or {}
        if option_attrs.get("publicly_available") is False:
            continue
        option = {
            "id": str(resource.get("id") or ""),
            "name": clean_text(option_attrs.get("name")) or None,
            "price_cents": option_attrs.get("price_cents"),
            "price_currency": option_attrs.get("price_currency"),
            "price_currency_symbol": option_attrs.get("price_currency_symbol"),
            "price_formatted": option_attrs.get("price_formatted"),
            "maximum_capacity": option_attrs.get("maximum_capacity"),
            "available_capacity": option_attrs.get("available_capacity"),
            "at_maximum_capacity": option_attrs.get("at_maximum_capacity"),
            "waitlist": option_attrs.get("waitlist"),
        }
        registration_options.append(
            {key: value for key, value in option.items() if value not in (None, "")}
        )

    location_resource = related_resource(signup, "signup_location", included)
    location, structured_location = format_location(location_resource)
    description = clean_text(attrs.get("description"))
    ministries, audiences, event_category, event_priority = infer_labels(title, categories, description)
    all_day = bool(time_attrs.get("all_day"))
    signup_time_id = str(time_resource.get("id") or "")
    registration_open = attrs.get("open")
    registration_closed = attrs.get("closed")
    at_capacity = attrs.get("at_maximum_capacity")

    status_bits: list[str] = []
    if registration_open is True:
        status_bits.append("Registration is open.")
    elif registration_closed is True or registration_open is False:
        status_bits.append("Registration is not currently open.")
    if at_capacity is True:
        status_bits.append("Registration is at maximum capacity.")

    details = description
    if status_bits:
        details = "\n\n".join(value for value in [description, " ".join(status_bits)] if value)

    return {
        "id": stable_registration_event_id(signup_id, signup_time_id, start),
        "uid": f"registrations-{signup_id}-{signup_time_id}@planningcenter",
        "title": title,
        "summary": short_summary(description) or f"Upcoming Urbancrest event: {title}.",
        "start": iso_value(start),
        "end": iso_value(end),
        "sort_start_utc": utc_sort_value(start),
        "sort_end_utc": utc_sort_value(end),
        "display_when": display_when(start, end, all_day),
        "all_day": all_day,
        "location": location,
        "location_structured": structured_location,
        "description": description,
        "details": details,
        "details_source": "planning_center_registrations_api",
        "planning_center_signup_id": signup_id,
        "planning_center_signup_time_id": signup_time_id,
        "registration_url": registration_url,
        # This flag means an exact public registration action exists. Open/closed/full
        # state remains separate so the runtime can describe those states precisely.
        "registration_available": True,
        "registration_open": registration_open,
        "registration_closed": registration_closed,
        "registration_at_maximum_capacity": at_capacity,
        "registration_open_at": attrs.get("open_at"),
        "registration_close_at": attrs.get("close_at"),
        "registration_maximum_capacity": attrs.get("maximum_capacity"),
        "registration_categories": categories,
        "registration_options": registration_options,
        "info_url": registration_url,
        "image_url": attrs.get("logo_url"),
        "ministries": ministries,
        "audiences": audiences,
        "event_category": event_category,
        "event_priority": event_priority,
        "collection": "main_events",
        "status": "published",
        "event_source": "planning_center_registrations_api",
        "event_sources": ["planning_center_registrations_api"],
    }


def registration_url_match(existing: dict[str, Any], incoming: dict[str, Any]) -> bool:
    left = normalize_url(existing.get("registration_url"))
    right = normalize_url(incoming.get("registration_url"))
    return bool(left and right and left == right)


def title_date_match(existing: dict[str, Any], incoming: dict[str, Any]) -> bool:
    if normalize_text(existing.get("title")) != normalize_text(incoming.get("title")):
        return False
    return bool(
        local_date_key(existing.get("start") or existing.get("sort_start_utc"))
        and local_date_key(existing.get("start") or existing.get("sort_start_utc"))
        == local_date_key(incoming.get("start") or incoming.get("sort_start_utc"))
    )


def merge_sources(existing: dict[str, Any], incoming: dict[str, Any]) -> list[str]:
    values: list[str] = []
    values.extend(existing.get("event_sources") or [])
    if existing.get("event_source"):
        values.append(str(existing["event_source"]))
    # Infer the legacy source when no explicit per-event source was present.
    if not values:
        values.append("planning_center_ical")
        if existing.get("planning_center_event_id") or existing.get("details_source") == "planning_center_calendar_api":
            values.append("planning_center_calendar_api")
    values.extend(incoming.get("event_sources") or [])
    if incoming.get("event_source"):
        values.append(str(incoming["event_source"]))
    return unique(values)


def merge_event(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    merged["event_sources"] = merge_sources(existing, incoming)
    merged["event_source"] = "merged" if len(merged["event_sources"]) > 1 else merged["event_sources"][0]

    # Registrations owns signup state and the signup URL.
    for key in (
        "planning_center_signup_id",
        "planning_center_signup_time_id",
        "registration_url",
        "registration_available",
        "registration_open",
        "registration_closed",
        "registration_at_maximum_capacity",
        "registration_open_at",
        "registration_close_at",
        "registration_maximum_capacity",
        "registration_categories",
        "registration_options",
    ):
        if key in incoming:
            merged[key] = incoming[key]

    # Prefer rich Registrations content when the calendar copy is blank/shorter.
    for key in ("description", "details", "summary"):
        incoming_value = clean_text(incoming.get(key))
        existing_value = clean_text(existing.get(key))
        if incoming_value and (not existing_value or len(incoming_value) > len(existing_value)):
            merged[key] = incoming.get(key)
            if key == "details":
                merged["details_source"] = "planning_center_registrations_api"

    for key in ("image_url", "location", "location_structured"):
        if incoming.get(key) and not existing.get(key):
            merged[key] = incoming[key]

    # Preserve stronger existing classification, but supplement searchable metadata.
    merged["ministries"] = unique([*(existing.get("ministries") or []), *(incoming.get("ministries") or [])])
    merged["audiences"] = unique([*(existing.get("audiences") or []), *(incoming.get("audiences") or [])])
    if incoming.get("registration_categories"):
        merged["registration_categories"] = unique(
            [*(existing.get("registration_categories") or []), *(incoming.get("registration_categories") or [])]
        )
    merged["event_priority"] = max(int(existing.get("event_priority") or 0), int(incoming.get("event_priority") or 0))
    return merged


def event_start_ms(event: dict[str, Any]) -> float:
    dt = parse_dt(event.get("sort_start_utc") or event.get("start"))
    return dt.timestamp() if dt else float("inf")


def annotate_chronology(events: list[dict[str, Any]]) -> None:
    events.sort(key=lambda event: (event_start_ms(event), normalize_text(event.get("title"))))
    for index, event in enumerate(events, start=1):
        event["chronological_rank"] = index


def merge_registration_events(
    registry: dict[str, Any],
    registration_events: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, int]]:
    events = [dict(event) for event in (registry.get("events") or []) if isinstance(event, dict)]
    enriched = 0
    added = 0

    for incoming in registration_events:
        match_index = next((i for i, event in enumerate(events) if registration_url_match(event, incoming)), None)
        if match_index is None:
            match_index = next((i for i, event in enumerate(events) if title_date_match(event, incoming)), None)
        if match_index is None:
            events.append(incoming)
            added += 1
        else:
            events[match_index] = merge_event(events[match_index], incoming)
            enriched += 1

    # Re-apply the existing main-event selection policy after adding Registrations.
    # Priority >= 80 is protected, matching sync_events.py. Registrations-only
    # events are assigned at least priority 80 because this feed represents the
    # site's public main-events source.
    if MAX_MAIN_EVENTS > 0 and len(events) > MAX_MAIN_EVENTS:
        protected = [event for event in events if int(event.get("event_priority") or 0) >= 80]
        lower_priority = [event for event in events if int(event.get("event_priority") or 0) < 80]
        protected.sort(key=lambda event: (event_start_ms(event), normalize_text(event.get("title"))))
        lower_priority.sort(
            key=lambda event: (
                -int(event.get("event_priority") or 0),
                event_start_ms(event),
                normalize_text(event.get("title")),
            )
        )
        if len(protected) >= MAX_MAIN_EVENTS:
            events = protected[:MAX_MAIN_EVENTS]
        else:
            events = protected + lower_priority[: MAX_MAIN_EVENTS - len(protected)]

    annotate_chronology(events)

    updated = dict(registry)
    previous_source = str(registry.get("source") or "planning_center_ical")
    source_parts = unique([*previous_source.split("+"), "registrations_api"])
    updated["version"] = "1.5.4"
    updated["generated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    updated["source"] = "+".join(source_parts)
    updated["registrations_api"] = {
        "status": "ok",
        "api_version": API_VERSION,
        "signup_time_strategy": "next_signup_time_then_signup_times_preserve_relationship_linkage",
        "future_signup_count": len(registration_events),
        "added_registration_only_events": added,
        "enriched_existing_events": enriched,
        "category_allowlist": sorted(CATEGORY_ALLOWLIST),
        "category_denylist": sorted(CATEGORY_DENYLIST),
    }
    updated["event_count"] = len(events)
    updated["events"] = events
    return updated, {"added": added, "enriched": enriched, "total": len(events)}


def write_upcoming_index(registry: dict[str, Any]) -> None:
    """Keep the human-readable generated event index aligned with the merged registry."""
    EVENT_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    generated_at = str(registry.get("generated_at") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))
    lines = [
        "---",
        "id: events.upcoming.live",
        "version: 1.5.4",
        "status: published",
        "priority: 100",
        "title: Upcoming Events",
        "summary: Major and ministry events synchronized from Urbancrest's calendar and Planning Center Registrations.",
        "category: [events]",
        "intent:",
        "  primary: upcoming_events",
        "  secondary: [calendar, schedule, whats_happening, next_ministry_event, registration]",
        "audience: [everyone]",
        "answer_style: helpful",
        "confidence: high",
        "tags: [events, calendar, registrations, upcoming, schedule]",
        "resources:",
        "  - events.live",
        "calendar_sort_order: sort_start_utc_ascending",
        f"last_generated: {generated_at}",
        "---",
        "",
        "# Upcoming Events",
        "",
        "This index combines Urbancrest's live calendar with public Planning Center Registrations events.",
        "Events are listed in ascending chronological order.",
        "",
    ]
    events = registry.get("events") or []
    if not events:
        lines.extend(["There are currently no upcoming events listed.", ""])
    else:
        for event in events:
            title = str(event.get("title") or "Untitled Event")
            lines.extend([f"## {title}", ""])
            if event.get("event_category"):
                lines.extend([f"**Category:** {str(event['event_category']).replace('_', ' ').title()}", ""])
            if event.get("display_when"):
                lines.extend([f"**When:** {event['display_when']}", ""])
            if event.get("location"):
                lines.extend([f"**Where:** {event['location']}", ""])
            if event.get("registration_url"):
                lines.extend([f"**Registration:** {event['registration_url']}", ""])
            elif event.get("info_url"):
                lines.extend([f"**More information:** {event['info_url']}", ""])
            if event.get("knowledge_file"):
                lines.extend([f"Detailed event file: `{event['knowledge_file']}`", ""])
    EVENT_INDEX_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    if not EVENT_REGISTRY_PATH.exists():
        raise RuntimeError(
            f"{EVENT_REGISTRY_PATH} does not exist. Run scripts/sync_events.py before sync_registrations.py."
        )

    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=LOOKAHEAD_DAYS)
    signups, fetch_meta = fetch_signups()
    included = fetch_meta["included"]

    registration_events: list[dict[str, Any]] = []
    skipped = 0
    skipped_reasons: Counter[str] = Counter()
    for signup in signups:
        diagnostics: dict[str, str] = {}
        event = signup_to_event(signup, included, now, cutoff, diagnostics)
        if event:
            registration_events.append(event)
        else:
            skipped += 1
            skipped_reasons[diagnostics.get("skip_reason", "unknown")] += 1

    registration_events.sort(key=event_start_ms)
    registry = yaml.safe_load(EVENT_REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    updated, stats = merge_registration_events(registry, registration_events)
    updated["registrations_api"]["signup_count_received"] = len(signups)
    updated["registrations_api"]["relationship_linkage_counts"] = relationship_linkage_counts(signups)
    updated["registrations_api"]["skipped_signup_count"] = skipped
    updated["registrations_api"]["skipped_reasons"] = dict(sorted(skipped_reasons.items()))
    updated["registrations_api"]["page_count"] = fetch_meta["page_count"]

    EVENT_REGISTRY_PATH.write_text(
        yaml.safe_dump(updated, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8",
    )
    write_upcoming_index(updated)

    print(
        "Registrations sync complete: "
        f"received {len(signups)} signups, selected {len(registration_events)} future public signups, "
        f"enriched {stats['enriched']}, added {stats['added']}, final main events {stats['total']}."
    )
    if skipped_reasons:
        print("Registrations skipped by reason: " + ", ".join(f"{key}={value}" for key, value in sorted(skipped_reasons.items())))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"sync_registrations.py failed: {exc}", file=sys.stderr)
        raise
