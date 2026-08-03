#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "runtime" / "search-index.json"

SKIP_MARKDOWN = {
    "knowledge/events/upcoming-events.md",
    "knowledge/small-groups/upcoming-small-groups.md",
}
SKIP_YAML = {
    "registry/events-live.yaml",
    "registry/small-groups-live.yaml",
    "registry/staff.yaml",
    "registry/staff-routing.yaml",
    "registry/action-links.yaml",
    "registry/schedule.yaml",
    "relationships/ministry-staff.yaml",
}


def as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if isinstance(value, dict):
        return [str(key) for key in value.keys()]
    return [str(value)]


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value).strip()
        if cleaned and cleaned.casefold() not in seen:
            seen.add(cleaned.casefold())
            result.append(cleaned)
    return result


def flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return "\n".join(f"{key}: {flatten_text(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "\n".join(flatten_text(item) for item in value)
    return str(value)


def truncate(value: str, limit: int = 2400) -> str:
    value = value.strip()
    return value if len(value) <= limit else value[: limit - 3].rstrip() + "..."


def event_activity_aliases(title: str) -> list[str]:
    """Create public-facing activity aliases from a calendar event title."""
    cleaned = re.sub(r"\s+", " ", str(title or "")).strip()
    if not cleaned:
        return []

    aliases = [cleaned]
    simplified = cleaned

    # Remove common calendar prefixes that people usually omit in questions.
    prefix_patterns = [
        r"^open\s+gym\s*[-:|]?\s*",
        r"^urbancrest\s*[-:|]?\s*",
        r"^weekly\s*[-:|]?\s*",
    ]
    for pattern in prefix_patterns:
        candidate = re.sub(pattern, "", simplified, flags=re.IGNORECASE).strip()
        if candidate and candidate.casefold() != simplified.casefold():
            aliases.append(candidate)
            simplified = candidate

    # Add a spaced variant for common compound activity names.
    for alias in list(aliases):
        match = re.search(r"\bpickleball\b", alias, flags=re.IGNORECASE)
        if match:
            replacement = "Pickle ball" if match.group(0)[:1].isupper() else "pickle ball"
            spaced = (
                alias[: match.start()]
                + replacement
                + alias[match.end() :]
            )
            if spaced.casefold() != alias.casefold():
                aliases.append(spaced)

    return unique(aliases)


def parse_markdown(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}, text.strip()
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return {}, text.strip()
    metadata = yaml.safe_load(parts[1]) or {}
    return metadata if isinstance(metadata, dict) else {}, parts[2].strip()


def intent_values(metadata: dict[str, Any]) -> list[str]:
    intent = metadata.get("intent")
    if isinstance(intent, dict):
        return unique(as_list(intent.get("primary")) + as_list(intent.get("secondary")))
    return unique(as_list(intent))


def record_base(
    *,
    record_id: str,
    record_type: str,
    path: str,
    title: str,
    summary: str = "",
    content: str = "",
    priority: int = 50,
    category: list[str] | None = None,
    intents: list[str] | None = None,
    tags: list[str] | None = None,
    search_terms: list[str] | None = None,
    ministries: list[str] | None = None,
    audiences: list[str] | None = None,
    resources: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    record = {
        "id": record_id,
        "record_type": record_type,
        "path": path,
        "title": title,
        "summary": summary,
        "content": truncate(content),
        "priority": int(priority or 0),
        "category": unique(category or []),
        "intents": unique(intents or []),
        "tags": unique(tags or []),
        "search_terms": unique(search_terms or []),
        "ministries": unique(ministries or []),
        "audiences": unique(audiences or []),
        "resources": unique(resources or []),
    }
    for key, value in extra.items():
        if value is not None and value != [] and value != "":
            record[key] = value
    return record


def markdown_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted((ROOT / "knowledge").rglob("*.md")):
        relative = path.relative_to(ROOT).as_posix()
        if relative in SKIP_MARKDOWN:
            continue
        if relative.startswith("knowledge/events/generated/"):
            continue
        if relative.startswith("knowledge/small-groups/generated/"):
            continue
        metadata, body = parse_markdown(path)
        status = str(metadata.get("status", "published"))
        if status not in {"published", "active"}:
            continue
        title = str(metadata.get("title") or path.stem.replace("-", " ").title())
        record_id = str(metadata.get("id") or relative)

        # Recurring schedules are authoritative in registry/schedule.yaml.
        # Keep legacy Markdown schedule files in the repository if desired, but
        # do not index them as competing runtime sources.
        if re.fullmatch(r"ministries\.[^.]+\.schedule", record_id):
            continue

        records.append(
            record_base(
                record_id=record_id,
                record_type="knowledge",
                path=relative,
                title=title,
                summary=str(metadata.get("summary") or ""),
                content=body,
                priority=int(metadata.get("priority") or 50),
                category=as_list(metadata.get("category")),
                intents=intent_values(metadata),
                tags=as_list(metadata.get("tags")),
                search_terms=as_list(metadata.get("search_terms")),
                ministries=as_list(metadata.get("ministries")),
                audiences=as_list(metadata.get("audience")),
                resources=as_list(metadata.get("resources")),
                status=status,
                staff_key=metadata.get("staff_key"),
                recommended_contact_staff_key=metadata.get("recommended_contact_staff_key"),
                related_staff_keys=as_list(metadata.get("related_staff_keys")),
                leadership_status=metadata.get("leadership_status"),
                open_role=metadata.get("open_role"),
                review_trigger=metadata.get("review_trigger"),
                answer_guidance=metadata.get("answer_guidance"),
                confidence=metadata.get("confidence"),
                authoritative=metadata.get("authoritative"),
                authoritative_for=as_list(metadata.get("authoritative_for")),
            )
        )
    return records



DAY_ORDER = {
    "monday": 1,
    "tuesday": 2,
    "wednesday": 3,
    "thursday": 4,
    "friday": 5,
    "saturday": 6,
    "sunday": 7,
}


def meeting_sort_key(meeting: dict[str, Any]) -> tuple[int, int, str]:
    day = str(meeting.get("day") or "").casefold()
    day_rank = DAY_ORDER.get(day, 99)
    raw_time = str(meeting.get("time") or "").strip()
    time_rank = 9999

    match = re.fullmatch(r"(\d{1,2}):(\d{2})\s*([AP]M)", raw_time, flags=re.IGNORECASE)
    if match:
        hour = int(match.group(1)) % 12
        minute = int(match.group(2))
        if match.group(3).upper() == "PM":
            hour += 12
        time_rank = hour * 60 + minute

    return (day_rank, time_rank, raw_time.casefold())


def format_meeting(meeting: dict[str, Any]) -> str:
    day = str(meeting.get("day") or "").strip()
    time = str(meeting.get("time") or "").strip()
    location = str(meeting.get("location") or "").strip()

    if day and time:
        text = f"{day} at {time}"
    else:
        text = day or time or "Schedule time not specified"

    if location:
        text += f" at {location}"
    return text


def schedule_question_terms(names: list[str]) -> list[str]:
    terms: list[str] = []
    for value in unique(names):
        terms.extend(
            [
                value,
                f"When does {value} meet?",
                f"When do {value} meet?",
                f"What time does {value} meet?",
                f"What time is {value}?",
                f"What is the {value} schedule?",
                f"What days does {value} meet?",
                f"When is {value}?",
                f"Does Urbancrest have {value}?",
                f"Do you offer {value}?",
                f"Is there {value} at Urbancrest?",
            ]
        )
    return unique(terms)


def schedule_records() -> list[dict[str, Any]]:
    path = ROOT / "registry/schedule.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    timezone_name = str(data.get("timezone") or "America/New_York")
    authoritative = bool(data.get("authoritative", True))
    top_guidance = str(data.get("answer_guidance") or "")
    ministries_config = data.get("ministries") or {}
    schedules = [item for item in (data.get("schedules") or []) if isinstance(item, dict)]

    records: list[dict[str, Any]] = []
    schedules_by_ministry: dict[str, list[dict[str, Any]]] = {}

    for item in schedules:
        schedule_id = str(item.get("id") or "").strip()
        if not schedule_id:
            continue

        ministry_key = str(item.get("ministry") or "churchwide").strip()
        ministry_config = ministries_config.get(ministry_key, {}) if isinstance(ministries_config, dict) else {}
        if not isinstance(ministry_config, dict):
            ministry_config = {}

        name = str(item.get("name") or schedule_id.replace(".", " ").title()).strip()
        schedule_aliases = unique([name, *as_list(item.get("aliases"))])
        ministry_name = str(ministry_config.get("name") or ministry_key.replace("_", " ").title()).strip()
        ministry_aliases = unique([ministry_name, *as_list(ministry_config.get("aliases"))])
        meetings = [meeting for meeting in (item.get("meetings") or []) if isinstance(meeting, dict)]
        meetings = sorted(meetings, key=meeting_sort_key)
        meeting_lines = [format_meeting(meeting) for meeting in meetings]
        seasonal_note = str(item.get("seasonal_note") or "").strip()
        answer_guidance = str(item.get("answer_guidance") or top_guidance).strip()

        content_lines = [f"{name} recurring schedule:"]
        content_lines.extend(f"- {line}" for line in meeting_lines)
        if seasonal_note:
            content_lines.append(f"Seasonal note: {seasonal_note}")

        summary = f"{name}: " + "; ".join(meeting_lines)
        if seasonal_note:
            summary += f". {seasonal_note}"

        recommended_contact = (
            item.get("recommended_contact_staff_key")
            or ministry_config.get("recommended_contact_staff_key")
        )
        show_staff_card = bool(
            item.get(
                "show_staff_card_on_schedule_queries",
                ministry_config.get("show_staff_card_on_schedule_queries", False),
            )
        )

        item_intents = unique(
            [
                "schedule",
                "weekly_schedule",
                "ministry_schedule",
                *as_list(item.get("intents")),
            ]
        )

        records.append(
            record_base(
                record_id=f"schedule.{schedule_id}",
                record_type="schedule",
                path="registry/schedule.yaml",
                title=name,
                summary=summary,
                content="\n".join(content_lines),
                priority=int(item.get("priority") or 115),
                category=["schedule", "recurring", ministry_key],
                intents=item_intents,
                tags=unique(
                    [
                        "schedule",
                        "recurring",
                        ministry_key,
                        name,
                        *schedule_aliases,
                        *as_list(item.get("tags")),
                    ]
                ),
                search_terms=schedule_question_terms(schedule_aliases),
                ministries=[ministry_key],
                audiences=as_list(item.get("audiences")),
                schedule_id=schedule_id,
                schedule_scope="activity",
                schedule_aliases=schedule_aliases,
                ministry_aliases=ministry_aliases,
                meetings=meetings,
                seasonal_note=seasonal_note,
                recommended_contact_staff_key=recommended_contact,
                show_staff_card_on_schedule_queries=show_staff_card,
                authoritative=authoritative,
                authoritative_for=unique(
                    [
                        "schedule",
                        "recurring_schedule",
                        "ministry_schedule",
                        *as_list(item.get("intents")),
                    ]
                ),
                confidence="high",
                timezone=timezone_name,
                answer_guidance=answer_guidance,
            )
        )

        schedules_by_ministry.setdefault(ministry_key, []).append(
            {
                "schedule_id": schedule_id,
                "name": name,
                "aliases": schedule_aliases,
                "meetings": meetings,
                "seasonal_note": seasonal_note,
                "priority": int(item.get("priority") or 115),
            }
        )

    # Aggregate each ministry so broad questions such as "When do kids meet?"
    # can return all of that ministry's recurring weekly activities.
    for ministry_key, ministry_schedules in schedules_by_ministry.items():
        ministry_config = ministries_config.get(ministry_key, {}) if isinstance(ministries_config, dict) else {}
        if not isinstance(ministry_config, dict):
            ministry_config = {}

        ministry_name = str(ministry_config.get("name") or ministry_key.replace("_", " ").title()).strip()
        ministry_aliases = unique([ministry_name, *as_list(ministry_config.get("aliases"))])
        content_lines = [f"{ministry_name} recurring schedule:"]
        all_meetings: list[dict[str, Any]] = []

        for item in sorted(
            ministry_schedules,
            key=lambda entry: (
                min((meeting_sort_key(m) for m in entry["meetings"]), default=(99, 9999, "")),
                entry["name"].casefold(),
            ),
        ):
            meeting_text = "; ".join(format_meeting(meeting) for meeting in item["meetings"])
            line = f"- {item['name']}: {meeting_text}"
            if item["seasonal_note"]:
                line += f". {item['seasonal_note']}"
            content_lines.append(line)
            all_meetings.extend(item["meetings"])

        recommended_contact = ministry_config.get("recommended_contact_staff_key")
        show_staff_card = bool(ministry_config.get("show_staff_card_on_schedule_queries", False))
        max_priority = max((entry["priority"] for entry in ministry_schedules), default=115)

        records.append(
            record_base(
                record_id=f"schedule.ministry.{ministry_key}",
                record_type="schedule",
                path="registry/schedule.yaml",
                title=f"{ministry_name} Weekly Schedule",
                summary=" ".join(content_lines[1:]),
                content="\n".join(content_lines),
                priority=max(118, min(max_priority + 3, 126)),
                category=["schedule", "recurring", "ministry", ministry_key],
                intents=["schedule", "weekly_schedule", "ministry_schedule"],
                tags=unique(
                    [
                        "schedule",
                        "recurring",
                        "ministry",
                        ministry_key,
                        *ministry_aliases,
                    ]
                ),
                search_terms=schedule_question_terms(ministry_aliases),
                ministries=[ministry_key],
                schedule_scope="ministry",
                ministry_aliases=ministry_aliases,
                schedule_ids=[entry["schedule_id"] for entry in ministry_schedules],
                meetings=sorted(all_meetings, key=meeting_sort_key),
                recommended_contact_staff_key=recommended_contact,
                show_staff_card_on_schedule_queries=show_staff_card,
                authoritative=authoritative,
                authoritative_for=["schedule", "recurring_schedule", "ministry_schedule"],
                confidence="high",
                timezone=timezone_name,
                answer_guidance=top_guidance,
            )
        )

    # Overall recurring weekly schedule.
    weekly_lines = ["Urbancrest regular weekly schedule:"]
    all_meetings: list[dict[str, Any]] = []
    schedule_ids: list[str] = []

    for item in sorted(
        schedules,
        key=lambda entry: (
            min(
                (
                    meeting_sort_key(meeting)
                    for meeting in (entry.get("meetings") or [])
                    if isinstance(meeting, dict)
                ),
                default=(99, 9999, ""),
            ),
            str(entry.get("name") or "").casefold(),
        ),
    ):
        name = str(item.get("name") or item.get("id") or "Schedule")
        meetings = [meeting for meeting in (item.get("meetings") or []) if isinstance(meeting, dict)]
        meeting_text = "; ".join(format_meeting(meeting) for meeting in sorted(meetings, key=meeting_sort_key))
        line = f"- {name}: {meeting_text}"
        seasonal_note = str(item.get("seasonal_note") or "").strip()
        if seasonal_note:
            line += f". {seasonal_note}"
        weekly_lines.append(line)
        all_meetings.extend(meetings)
        if item.get("id"):
            schedule_ids.append(str(item.get("id")))

    records.append(
        record_base(
            record_id="schedule.weekly",
            record_type="schedule",
            path="registry/schedule.yaml",
            title="Urbancrest Weekly Schedule",
            summary="Regular Sunday and Wednesday recurring schedule for Urbancrest services and ministries.",
            content="\n".join(weekly_lines),
            priority=118,
            category=["schedule", "recurring", "about"],
            intents=["schedule", "weekly_schedule", "service_times", "visit"],
            tags=["schedule", "weekly schedule", "service times", "Sunday", "Wednesday"],
            search_terms=[
                "What is the Urbancrest weekly schedule?",
                "What happens each week at Urbancrest?",
                "When does Urbancrest meet?",
                "What time are Sunday services?",
                "What happens on Wednesday nights?",
                "What is the Wednesday schedule?",
            ],
            schedule_scope="churchwide",
            schedule_ids=schedule_ids,
            meetings=sorted(all_meetings, key=meeting_sort_key),
            authoritative=authoritative,
            authoritative_for=unique(
                [
                    "schedule",
                    "recurring_schedule",
                    "weekly_schedule",
                    *as_list(data.get("source_of_truth_for")),
                ]
            ),
            confidence="high",
            timezone=timezone_name,
            answer_guidance=top_guidance,
        )
    )

    return records


def event_records() -> list[dict[str, Any]]:
    path = ROOT / "registry/events-live.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    records: list[dict[str, Any]] = []
    for event in data.get("events", []):
        event_id = str(event.get("id") or "")
        title = str(event.get("title") or "Untitled Event")
        description = str(event.get("description") or "")
        details = str(event.get("details") or "")
        content = "\n\n".join(
            value
            for value in (
                description,
                f"Details:\n{details}" if details else "",
            )
            if value
        )
        activity_aliases = event_activity_aliases(title)
        normalized_title = title.casefold()
        routine_service_occurrence = (
            "sunday morning services" in normalized_title
            or "sunday worship service" in normalized_title
        )
        event_priority = int(event.get("event_priority") or 50)
        if routine_service_occurrence:
            event_priority = min(event_priority, 20)

        records.append(
            record_base(
                record_id=f"events.live.{event_id}",
                record_type="event",
                path=str(event.get("knowledge_file") or "registry/events-live.yaml"),
                title=title,
                summary=str(event.get("summary") or ""),
                content=content,
                priority=event_priority,
                category=["events", str(event.get("event_category") or "general_event")],
                intents=[
                    "event_details",
                    "upcoming_events",
                    "calendar",
                    "next_ministry_event",
                    "activity_availability",
                ],
                tags=[
                    "event",
                    "calendar",
                    "upcoming",
                    "activity",
                    str(event.get("event_category") or "general_event"),
                    *activity_aliases,
                ],
                search_terms=unique(
                    [
                        title,
                        f"When is {title}?",
                        f"Tell me about {title}",
                        f"What are the details for {title}?",
                        f"What is the menu for {title}?",
                        f"How do I register for {title}?",
                    ]
                    + [
                        phrase
                        for alias in activity_aliases
                        for phrase in (
                            alias,
                            f"Does Urbancrest have {alias}?",
                            f"Does Urbancrest offer {alias}?",
                            f"Do you have {alias}?",
                            f"Do you offer {alias}?",
                            f"Is there {alias} at Urbancrest?",
                            f"Can I participate in {alias}?",
                            f"Can I play {alias} at Urbancrest?",
                        )
                    ]
                ),
                ministries=as_list(event.get("ministries")),
                audiences=as_list(event.get("audiences")),
                event_id=event_id,
                activity_aliases=activity_aliases,
                event_category=event.get("event_category"),
                event_start=event.get("start"),
                event_end=event.get("end"),
                sort_start_utc=event.get("sort_start_utc"),
                sort_end_utc=event.get("sort_end_utc"),
                location=event.get("location"),
                details=event.get("details"),
                details_source=event.get("details_source"),
                planning_center_event_id=event.get("planning_center_event_id"),
                planning_center_event_instance_id=event.get("planning_center_event_instance_id"),
                planning_center_event_time_id=event.get("planning_center_event_time_id"),
                registration_url=event.get("registration_url"),
                info_url=event.get("info_url"),
                image_url=event.get("image_url"),
                knowledge_file=event.get("knowledge_file"),
                chronological_rank=event.get("chronological_rank"),
                routine_schedule_occurrence=routine_service_occurrence,
                retrieval_exclude_for_intents=(
                    ["service_times", "sunday_service_times", "weekly_schedule"]
                    if routine_service_occurrence
                    else []
                ),
            )
        )
    return records


def group_records() -> list[dict[str, Any]]:
    path = ROOT / "registry/small-groups-live.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    records: list[dict[str, Any]] = []
    for group in data.get("groups", []):
        group_id = str(group.get("id") or "")
        title = str(group.get("title") or "Untitled Small Group")
        meetings = group.get("future_meetings") or []
        schedule_lines = [str(item.get("display_when") or item.get("start") or "") for item in meetings if isinstance(item, dict)]
        content = "\n\n".join(
            filter(
                None,
                [
                    str(group.get("description") or ""),
                    f"Details:\n{group.get('details')}" if group.get("details") else "",
                    "Upcoming meetings:\n" + "\n".join(schedule_lines),
                ],
            )
        )
        next_meeting = group.get("next_meeting") or {}
        records.append(
            record_base(
                record_id=f"small_groups.live.{group_id}",
                record_type="small_group",
                path=str(group.get("knowledge_file") or "registry/small-groups-live.yaml"),
                title=title,
                summary=str(group.get("summary") or ""),
                content=content,
                priority=int(group.get("event_priority") or 20),
                category=["small_groups"],
                intents=["small_groups", "small_group_details", "next_small_group_meeting", "group_schedule"],
                tags=["small_group", "groups", "calendar", "recurring"],
                search_terms=[title, f"When does {title} meet?", f"Tell me about {title}"],
                ministries=as_list(group.get("ministries")),
                audiences=as_list(group.get("audiences")),
                group_id=group_id,
                next_meeting=next_meeting,
                future_meetings=meetings,
                sort_start_utc=next_meeting.get("sort_start_utc") if isinstance(next_meeting, dict) else None,
                sort_end_utc=next_meeting.get("sort_end_utc") if isinstance(next_meeting, dict) else None,
                location=group.get("location"),
                details=group.get("details"),
                details_source=group.get("details_source"),
                planning_center_event_id=group.get("planning_center_event_id"),
                planning_center_event_instance_id=group.get("planning_center_event_instance_id"),
                planning_center_event_time_id=group.get("planning_center_event_time_id"),
                registration_url=group.get("registration_url"),
                info_url=group.get("info_url"),
                knowledge_file=group.get("knowledge_file"),
            )
        )
    return records


def staff_records() -> list[dict[str, Any]]:
    staff_data = yaml.safe_load((ROOT / "registry/staff.yaml").read_text(encoding="utf-8")) or {}
    route_data = yaml.safe_load((ROOT / "registry/staff-routing.yaml").read_text(encoding="utf-8")) or {}
    directory = staff_data.get("staff", {})
    routing = route_data.get("routing", {})
    records: list[dict[str, Any]] = []
    for key, person in directory.items():
        route = routing.get(key, {})
        name = str(person.get("name") or key)
        role = str(person.get("role") or "Staff")
        aliases = as_list(route.get("aliases"))
        topics = as_list(route.get("topics"))
        ministries = as_list(route.get("ministries"))
        answer_guidance = str(route.get("answer_guidance") or "")
        staff_content = (
            f"Display name: {person.get('display_name', name)}\n"
            f"Role: {role}\n"
            f"Ministries: {', '.join(ministries)}\n"
            f"Topics: {', '.join(topics)}"
        )
        if answer_guidance:
            staff_content += f"\nAnswer guidance: {answer_guidance}"

        records.append(
            record_base(
                record_id=f"staff.{key}",
                record_type="staff_route",
                path="registry/staff-routing.yaml",
                title=name,
                summary=f"{name} serves as {role}. Full biography and fun facts are loaded from Base44 Staff when relevant.",
                content=staff_content,
                priority=90,
                category=["staff"],
                intents=["staff", "staff_details", "staff_routing", "ministry_contact"],
                tags=["staff", role, *ministries],
                search_terms=[name, str(person.get("display_name") or ""), role, *aliases, *topics],
                ministries=ministries,
                staff_key=key,
                display_name=person.get("display_name"),
                role=role,
                pastoral_staff=person.get("pastoral_staff", False),
                show_card=route.get("show_card", True),
                profile_source="base44.Staff",
                answer_guidance=answer_guidance,
            )
        )
    return records


def action_link_records() -> list[dict[str, Any]]:
    data = yaml.safe_load((ROOT / "registry/action-links.yaml").read_text(encoding="utf-8")) or {}
    records: list[dict[str, Any]] = []
    for key, link in data.get("links", {}).items():
        label = str(link.get("label") or key)
        intents = as_list(link.get("intents"))
        aliases = as_list(link.get("aliases"))
        configured_search_terms = as_list(link.get("search_terms"))
        bundle = str(link.get("bundle") or "")
        answer_guidance = str(link.get("answer_guidance") or "")

        content_lines = [
            f"Label: {label}",
            f"URL: {link.get('url', '')}",
            f"Intents: {', '.join(intents)}",
        ]
        if aliases:
            content_lines.append(f"Aliases: {', '.join(aliases)}")
        if bundle:
            content_lines.append(f"Bundle: {bundle}")
        if answer_guidance:
            content_lines.append(f"Answer guidance: {answer_guidance}")

        records.append(
            record_base(
                record_id=f"action_link.{key}",
                record_type="action_link",
                path="registry/action-links.yaml",
                title=label,
                summary=f"Approved Urbancrest action link for {', '.join(intents)}.",
                content="\n".join(content_lines),
                priority=int(link.get("priority") or 50),
                category=["action_link"],
                intents=intents,
                tags=["action", "link", *intents, *aliases],
                search_terms=unique([label, *intents, *aliases, *configured_search_terms]),
                action_key=key,
                url=link.get("url"),
                external=link.get("external", False),
                church_center_modal=link.get("church_center_modal", False),
                bundle=bundle,
                include_with_bundle=bool(link.get("include_with_bundle", False)),
                answer_guidance=answer_guidance,
            )
        )
    return records


def relationship_records() -> list[dict[str, Any]]:
    data = yaml.safe_load((ROOT / "relationships/ministry-staff.yaml").read_text(encoding="utf-8")) or {}
    records: list[dict[str, Any]] = []
    for relationship in data.get("relationships", []):
        ministry = str(relationship.get("ministry") or "")
        label = str(relationship.get("label") or ministry.replace("_", " ").title())
        aliases = as_list(relationship.get("aliases"))
        topics = as_list(relationship.get("topics"))
        primary = str(relationship.get("primary_staff_key") or "")
        recommended = str(relationship.get("recommended_contact_staff_key") or "")
        selected_staff_key = primary or recommended
        related = as_list(relationship.get("related_staff_keys"))
        leadership_status = str(relationship.get("leadership_status") or "staffed")
        open_role = str(relationship.get("open_role") or "")
        answer_guidance = str(relationship.get("answer_guidance") or "")

        summary_parts = [f"Staff ownership relationship for {label}."]
        if leadership_status in {"vacant", "transitional"}:
            summary_parts.append(f"Leadership status: {leadership_status}.")
        if open_role:
            summary_parts.append(f"Open role: {open_role}.")
        if selected_staff_key:
            summary_parts.append(f"Recommended staff key: {selected_staff_key}.")
        summary = " ".join(summary_parts)

        content_lines = [
            f"Area: {label}",
            f"Canonical area key: {ministry}",
            f"Leadership status: {leadership_status}",
            f"Primary staff key: {primary or 'none'}",
            f"Recommended contact staff key: {recommended or 'none'}",
            f"Related staff keys: {', '.join(related)}",
        ]
        if aliases:
            content_lines.append(f"Routing aliases: {', '.join(aliases)}")
        if topics:
            content_lines.append(f"Routing topics: {', '.join(topics)}")
        if open_role:
            content_lines.append(f"Open role: {open_role}")
        if answer_guidance:
            content_lines.append(f"Answer guidance: {answer_guidance}")

        base_terms = unique([label, ministry.replace("_", " "), *aliases, *topics])
        ownership_terms: list[str] = []
        for term in base_terms:
            ownership_terms.extend(
                [
                    term,
                    f"who oversees {term}",
                    f"who leads {term}",
                    f"who handles {term}",
                    f"who do I contact about {term}",
                    f"who is the point person for {term}",
                ]
            )
        if open_role:
            ownership_terms.append(open_role)

        records.append(
            record_base(
                record_id=f"relationship.ministry_staff.{ministry}",
                record_type="relationship",
                path="relationships/ministry-staff.yaml",
                title=f"{label} staff relationship",
                summary=summary,
                content="\n".join(content_lines),
                priority=105 if leadership_status in {"vacant", "transitional"} else 90,
                category=["relationship", "staff"],
                intents=["ministry_contact", "staff_routing", "staff_ownership"],
                tags=[ministry, label, leadership_status, *aliases],
                search_terms=unique(ownership_terms),
                ministries=[ministry],
                staff_key=selected_staff_key,
                primary_staff_key=primary,
                recommended_contact_staff_key=recommended,
                related_staff_keys=related,
                leadership_status=leadership_status,
                open_role=open_role,
                answer_guidance=answer_guidance,
                routing_aliases=aliases,
                routing_topics=topics,
                area_label=label,
            )
        )
    return records


def generic_yaml_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for root_name in ("registry", "relationships", "intents"):
        for path in sorted((ROOT / root_name).glob("*.yaml")):
            relative = path.relative_to(ROOT).as_posix()
            if relative in SKIP_YAML:
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if data is None:
                continue
            title = path.stem.replace("-", " ").replace("_", " ").title()
            records.append(
                record_base(
                    record_id=f"file.{relative}",
                    record_type="routing" if root_name == "intents" else "registry",
                    path=relative,
                    title=title,
                    summary=f"Structured {root_name} data from {relative}.",
                    content=flatten_text(data),
                    priority=65 if root_name == "intents" else 60,
                    category=[root_name],
                    intents=[path.stem] if root_name == "intents" else [],
                    tags=[root_name, path.stem],
                    search_terms=[title, path.stem.replace("-", " ")],
                )
            )
    return records


def main() -> None:
    records = []
    records.extend(markdown_records())
    records.extend(schedule_records())
    records.extend(event_records())
    records.extend(group_records())
    records.extend(staff_records())
    records.extend(action_link_records())
    records.extend(relationship_records())
    records.extend(generic_yaml_records())

    deduped: dict[str, dict[str, Any]] = {}
    for record in records:
        deduped[record["id"]] = record
    records = sorted(
        deduped.values(),
        key=lambda item: (-int(item.get("priority", 0)), item.get("record_type", ""), item.get("title", "").casefold()),
    )

    manifest = yaml.safe_load((ROOT / "manifest.yaml").read_text(encoding="utf-8")) or {}
    payload = {
        "schema_version": "1.0",
        "repository": manifest.get("repository", "urbancrest-knowledge"),
        "repository_version": manifest.get("version"),
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "timezone": "America/New_York",
        "record_count": len(records),
        "config": {
            "personality": (ROOT / "AI_PERSONALITY.md").read_text(encoding="utf-8"),
            "style_guide": (ROOT / "STYLE_GUIDE.md").read_text(encoding="utf-8"),
            "max_retrieval_records": 8,
            "staff_profile_source": "base44.Staff",
            "admin_knowledge_source": "base44.KnowledgeEntry",
        },
        "source_rules": yaml.safe_load((ROOT / "registry/runtime-sources.yaml").read_text(encoding="utf-8")),
        "records": records,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(records)} retrieval records to {OUTPUT.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
