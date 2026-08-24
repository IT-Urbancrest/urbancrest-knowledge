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
    content_limit: int | None = 2400,
    **extra: Any,
) -> dict[str, Any]:
    record = {
        "id": record_id,
        "record_type": record_type,
        "path": path,
        "title": title,
        "summary": summary,
        "content": content.strip() if content_limit is None else truncate(content, content_limit),
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


def markdown_record_type(
    relative: str,
    metadata: dict[str, Any],
) -> str:
    """Determine the search-index record type for a Markdown file.

    Explicit record_type frontmatter wins when present. Sermon files
    historically rely on their directory structure instead.
    """
    explicit = str(metadata.get("record_type") or "").strip()
    if explicit:
        return explicit

    if relative.startswith("knowledge/sermons/series/"):
        return "sermon_series"

    if relative.startswith("knowledge/sermons/"):
        return "sermon"

    return "knowledge"


def markdown_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    # Parse Markdown first so sermon-series metadata can be resolved
    # before individual sermon records are built.
    sources: list[tuple[Path, str, dict[str, Any], str]] = []

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

        sources.append((path, relative, metadata, body))

    # Build a series_id -> title lookup for individual sermon records.
    series_titles: dict[str, str] = {}

    for path, relative, metadata, body in sources:
        record_type = markdown_record_type(relative, metadata)
        if record_type != "sermon_series":
            continue

        series_id = str(metadata.get("series_id") or "").strip()
        title = str(metadata.get("title") or path.stem.replace("-", " ").title())
        if series_id:
            series_titles[series_id] = title

    for path, relative, metadata, body in sources:
        title = str(metadata.get("title") or path.stem.replace("-", " ").title())
        status = str(metadata.get("status", "published"))
        record_type = markdown_record_type(relative, metadata)

        category = as_list(metadata.get("category"))
        intents = intent_values(metadata)
        tags = as_list(metadata.get("tags"))
        search_terms = as_list(metadata.get("search_terms"))
        topics = as_list(metadata.get("topics"))

        extra: dict[str, Any] = {
            "status": status,
            "staff_key": metadata.get("staff_key"),
            "recommended_contact_staff_key": metadata.get("recommended_contact_staff_key"),
            "related_staff_keys": as_list(metadata.get("related_staff_keys")),
            "leadership_status": metadata.get("leadership_status"),
            "open_role": metadata.get("open_role"),
            "review_trigger": metadata.get("review_trigger"),
            "answer_guidance": metadata.get("answer_guidance"),
            "confidence": metadata.get("confidence"),
            "authoritative": metadata.get("authoritative"),
            "authoritative_for": as_list(metadata.get("authoritative_for")),
        }

        if record_type == "sermon":
            sermon_date = metadata.get("sermon_date") or metadata.get("date")
            series_id = str(metadata.get("series_id") or "").strip()
            series_title = metadata.get("series_title") or series_titles.get(series_id)

            tags = unique([*tags, "sermon", *topics])
            search_terms = unique([*search_terms, *topics])

            if "sermon" not in intents:
                intents.append("sermon")

            extra.update({
                "sermon_date": str(sermon_date) if sermon_date is not None else None,
                "date": str(sermon_date) if sermon_date is not None else None,
                "speaker": metadata.get("speaker"),
                "series_id": series_id or None,
                "series_title": series_title,
                "primary_scripture": metadata.get("primary_scripture"),
                "notes_url": metadata.get("notes_url"),
                "topics": topics,
                "title_source": metadata.get("title_source"),
                "outline_source": metadata.get("outline_source"),
                "summary_source": metadata.get("summary_source"),
            })

        elif record_type == "sermon_series":
            series_id = str(metadata.get("series_id") or "").strip()

            # Build the series message list automatically from individual
            # sermon files whose series_id matches this series.
            normalized_sermons: list[dict[str, Any]] = []

            if series_id:
                for sermon_path, sermon_relative, sermon_metadata, sermon_body in sources:
                    sermon_record_type = markdown_record_type(sermon_relative, sermon_metadata)
                    if sermon_record_type != "sermon":
                        continue

                    sermon_series_id = str(sermon_metadata.get("series_id") or "").strip()
                    if sermon_series_id != series_id:
                        continue

                    sermon_date = sermon_metadata.get("sermon_date") or sermon_metadata.get("date")
                    sermon_title = str(
                        sermon_metadata.get("title")
                        or sermon_path.stem.replace("-", " ").title()
                    )

                    normalized_sermons.append({
                        "date": str(sermon_date) if sermon_date is not None else "",
                        "title": sermon_title,
                        "speaker": str(sermon_metadata.get("speaker") or ""),
                        "primary_scripture": str(sermon_metadata.get("primary_scripture") or ""),
                    })

            normalized_sermons.sort(key=lambda sermon: sermon.get("date", ""))

            tags = unique([*tags, "sermon", "sermon series"])
            if "sermon_series" not in intents:
                intents.append("sermon_series")

            extra.update({
                "series_id": series_id or None,
                "series_status": metadata.get("series_status"),
                "start_date": str(metadata.get("start_date")) if metadata.get("start_date") is not None else None,
                "end_date": str(metadata.get("end_date")) if metadata.get("end_date") is not None else None,
                "primary_scripture": metadata.get("primary_scripture"),
                "sermons": normalized_sermons,
                "artwork_url": metadata.get("artwork_url"),
                "image_url": metadata.get("image_url"),
                "series_artwork_url": metadata.get("series_artwork_url"),
            })

        records.append(
            record_base(
                record_id=str(metadata.get("id") or relative),
                record_type=record_type,
                path=relative,
                title=title,
                summary=str(metadata.get("summary") or ""),
                content=body,
                # Doctrine direct-answer handlers select named sections from belief articles.
                # Keep those articles complete so a section can never be cut mid-sentence by
                # the generic 2,400-character retrieval cap.
                content_limit=None if relative.startswith("knowledge/beliefs") else 2400,
                priority=int(metadata.get("priority") or 50),
                category=category,
                intents=intents,
                tags=tags,
                search_terms=search_terms,
                ministries=as_list(metadata.get("ministries")),
                audiences=as_list(metadata.get("audience")),
                resources=as_list(metadata.get("resources")),
                **extra,
            )
        )

    return records


def schedule_records() -> list[dict[str, Any]]:
    # schedule schema 2.1 compiler
    path = ROOT / "registry/schedule.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    schedules = [item for item in data.get("schedules", []) if isinstance(item, dict)]
    ministries = data.get("ministries", {}) if isinstance(data.get("ministries"), dict) else {}

    if not schedules:
        raise ValueError("registry/schedule.yaml must contain at least one schedule entry")

    def meeting_lines(meetings: Any) -> list[str]:
        lines: list[str] = []
        for meeting in meetings or []:
            if not isinstance(meeting, dict):
                continue
            day = str(meeting.get("day") or "").strip()
            time = str(meeting.get("time") or "").strip()
            location = str(meeting.get("location") or "").strip()
            text = day
            if time:
                text += f" at {time}" if text else time
            if location:
                text += f" in {location}" if text else location
            if text:
                lines.append(text)
        return lines

    def schedule_summary(name: str, meetings: Any, seasonal_note: str = "") -> str:
        lines = meeting_lines(meetings)
        if not lines:
            summary = f"{name} has a recurring schedule."
        elif len(lines) == 1:
            summary = f"{name} meets {lines[0]}."
        else:
            summary = f"{name} meets " + "; ".join(lines) + "."
        if seasonal_note:
            summary += f" {seasonal_note.strip()}"
        return summary

    records: list[dict[str, Any]] = []

    worship_schedule = next(
        (
            item
            for item in schedules
            if str(item.get("id") or "") == "worship.sunday"
            or (
                str(item.get("ministry") or "") == "worship"
                and any(
                    isinstance(meeting, dict)
                    and str(meeting.get("day") or "").casefold() == "sunday"
                    for meeting in item.get("meetings", [])
                )
            )
        ),
        None,
    )
    sunday_labels = unique(
        [
            str(meeting.get("time") or "").strip()
            for meeting in (worship_schedule or {}).get("meetings", [])
            if isinstance(meeting, dict)
            and str(meeting.get("day") or "").casefold() == "sunday"
            and str(meeting.get("time") or "").strip()
        ]
    )
    if not sunday_labels:
        raise ValueError("registry/schedule.yaml must contain Sunday worship times in schedules")

    if len(sunday_labels) == 1:
        sunday_summary = f"Sunday worship service is at {sunday_labels[0]}."
    elif len(sunday_labels) == 2:
        sunday_summary = f"Sunday worship services are at {sunday_labels[0]} and {sunday_labels[1]}."
    else:
        sunday_summary = f"Sunday worship services are at {', '.join(sunday_labels[:-1])}, and {sunday_labels[-1]}."

    weekly_lines = ["Regular recurring schedule:"]
    for schedule in schedules:
        name = str(schedule.get("name") or schedule.get("id") or "Recurring Schedule")
        lines = meeting_lines(schedule.get("meetings"))
        if lines:
            weekly_lines.append(f"{name}: {'; '.join(lines)}")
        seasonal_note = str(schedule.get("seasonal_note") or "").strip()
        if seasonal_note:
            weekly_lines.append(f"{name} seasonal note: {seasonal_note}")

    records.append(
        record_base(
            record_id="schedule.weekly",
            record_type="schedule",
            path="registry/schedule.yaml",
            title="Urbancrest Weekly Service Schedule",
            summary=sunday_summary,
            content="\n".join(weekly_lines),
            priority=120,
            category=["schedule", "about"],
            intents=["service_times", "sunday_service_times", "weekly_schedule", "visit", "schedule"],
            tags=["service times", "Sunday services", "Sunday worship", "weekly schedule"],
            search_terms=[
                "What time are Sunday services?",
                "What are your Sunday service times?",
                "When are Sunday services?",
                "What time does church start?",
                "What time is church?",
                "When does Urbancrest meet?",
                "Sunday worship times",
                "Sunday service times",
                "weekly schedule",
                "Wednesday schedule",
            ],
            authoritative=bool(data.get("authoritative", True)),
            authoritative_for=as_list(data.get("source_of_truth_for")),
            confidence="high",
            answer_guidance=data.get("answer_guidance"),
            sunday_service_times=sunday_labels,
            timezone=data.get("timezone", "America/New_York"),
            schedule_scope="churchwide",
        )
    )

    schedules_by_ministry: dict[str, list[dict[str, Any]]] = {}

    for schedule in schedules:
        schedule_id = str(schedule.get("id") or "").strip()
        if not schedule_id:
            raise ValueError("Every registry/schedule.yaml schedule entry must have an id")
        ministry = str(schedule.get("ministry") or "").strip()
        ministry_config = ministries.get(ministry, {}) if isinstance(ministries.get(ministry), dict) else {}
        name = str(schedule.get("name") or schedule_id.replace("_", " ").replace(".", " ").title())
        aliases = unique([*as_list(schedule.get("aliases")), *as_list(ministry_config.get("aliases"))])
        meetings = schedule.get("meetings") or []
        seasonal_note = str(schedule.get("seasonal_note") or "").strip()
        guidance = str(schedule.get("answer_guidance") or "").strip()
        ministry_name = str(ministry_config.get("name") or ministry.replace("_", " ").title()).strip()
        recommended_staff_key = (
            schedule.get("recommended_contact_staff_key")
            or ministry_config.get("recommended_contact_staff_key")
        )
        show_staff_card = schedule.get("show_staff_card_on_schedule_queries")
        if show_staff_card is None:
            show_staff_card = ministry_config.get("show_staff_card_on_schedule_queries", False)

        content_lines = [f"Recurring schedule: {name}"]
        for line in meeting_lines(meetings):
            content_lines.append(f"Meeting: {line}")
        if seasonal_note:
            content_lines.append(f"Seasonal note: {seasonal_note}")
        if guidance:
            content_lines.append(f"Answer guidance: {guidance}")

        intents = unique([*as_list(schedule.get("intents")), "schedule", "weekly_schedule"])
        tags = unique([*as_list(schedule.get("tags")), "schedule", "recurring", ministry])
        search_terms = unique(
            [
                name,
                *aliases,
                f"When does {name} meet?",
                f"What time does {name} meet?",
                f"What is the {name} schedule?",
            ]
        )

        records.append(
            record_base(
                record_id=f"schedule.{schedule_id}",
                record_type="schedule",
                path="registry/schedule.yaml",
                title=name,
                summary=schedule_summary(name, meetings, seasonal_note),
                content="\n".join(content_lines),
                priority=int(schedule.get("priority") or 110),
                category=["schedule", "ministry_schedule"],
                intents=intents,
                tags=tags,
                search_terms=search_terms,
                ministries=[ministry] if ministry else [],
                authoritative=bool(data.get("authoritative", True)),
                authoritative_for=as_list(data.get("source_of_truth_for")),
                confidence="high",
                answer_guidance=guidance or data.get("answer_guidance"),
                schedule_scope="activity",
                meetings=meetings,
                schedule_aliases=as_list(schedule.get("aliases")),
                ministry_aliases=as_list(ministry_config.get("aliases")),
                seasonal_note=seasonal_note,
                recommended_contact_staff_key=recommended_staff_key,
                show_staff_card_on_schedule_queries=bool(show_staff_card),
                timezone=data.get("timezone", "America/New_York"),
            )
        )
        if ministry:
            schedules_by_ministry.setdefault(ministry, []).append(schedule)

    for ministry, ministry_schedules in schedules_by_ministry.items():
        ministry_config = ministries.get(ministry, {}) if isinstance(ministries.get(ministry), dict) else {}
        ministry_name = str(ministry_config.get("name") or ministry.replace("_", " ").title())
        aliases = as_list(ministry_config.get("aliases"))
        recommended_staff_key = ministry_config.get("recommended_contact_staff_key")
        show_staff_card = bool(ministry_config.get("show_staff_card_on_schedule_queries", False))

        aggregate_lines = [f"Recurring schedules for {ministry_name}:"]
        aggregate_meetings: list[dict[str, Any]] = []
        seasonal_notes: list[str] = []
        for schedule in ministry_schedules:
            schedule_name = str(schedule.get("name") or schedule.get("id") or "Schedule")
            lines = meeting_lines(schedule.get("meetings"))
            if lines:
                aggregate_lines.append(f"{schedule_name}: {'; '.join(lines)}")
            aggregate_meetings.extend(
                meeting for meeting in schedule.get("meetings", []) if isinstance(meeting, dict)
            )
            seasonal_note = str(schedule.get("seasonal_note") or "").strip()
            if seasonal_note:
                seasonal_notes.append(seasonal_note)
                aggregate_lines.append(f"{schedule_name} seasonal note: {seasonal_note}")

        records.append(
            record_base(
                record_id=f"schedule.ministry.{ministry}",
                record_type="schedule",
                path="registry/schedule.yaml",
                title=f"{ministry_name} Schedule",
                summary=schedule_summary(ministry_name, aggregate_meetings, " ".join(unique(seasonal_notes))),
                content="\n".join(aggregate_lines),
                priority=max(int(item.get("priority") or 0) for item in ministry_schedules),
                category=["schedule", "ministry_schedule"],
                intents=["schedule", "weekly_schedule", "ministry_schedule"],
                tags=["schedule", "recurring", ministry, ministry_name],
                search_terms=unique(
                    [
                        ministry_name,
                        *aliases,
                        f"When does {ministry_name} meet?",
                        f"What is the {ministry_name} schedule?",
                    ]
                ),
                ministries=[ministry],
                authoritative=bool(data.get("authoritative", True)),
                authoritative_for=as_list(data.get("source_of_truth_for")),
                confidence="high",
                answer_guidance=data.get("answer_guidance"),
                schedule_scope="ministry",
                meetings=aggregate_meetings,
                schedule_aliases=aliases,
                ministry_aliases=aliases,
                seasonal_note=" ".join(unique(seasonal_notes)),
                recommended_contact_staff_key=recommended_staff_key,
                show_staff_card_on_schedule_queries=show_staff_card,
                timezone=data.get("timezone", "America/New_York"),
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
                display_when=event.get("display_when"),
                all_day=event.get("all_day"),
                location=event.get("location"),
                location_structured=event.get("location_structured"),
                details=event.get("details"),
                details_source=event.get("details_source"),
                planning_center_event_id=event.get("planning_center_event_id"),
                planning_center_event_instance_id=event.get("planning_center_event_instance_id"),
                planning_center_event_time_id=event.get("planning_center_event_time_id"),
                registration_url=event.get("registration_url"),
                registration_available=bool(event.get("registration_available", bool(event.get("registration_url")))),
                registration_open=event.get("registration_open"),
                registration_closed=event.get("registration_closed"),
                registration_at_maximum_capacity=event.get("registration_at_maximum_capacity"),
                registration_open_at=event.get("registration_open_at"),
                registration_close_at=event.get("registration_close_at"),
                registration_maximum_capacity=event.get("registration_maximum_capacity"),
                registration_categories=event.get("registration_categories"),
                registration_options=event.get("registration_options"),
                event_source=event.get("event_source"),
                event_sources=event.get("event_sources"),
                publicly_listed=event.get("publicly_listed"),
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
        records.append(
            record_base(
                record_id=f"action_link.{key}",
                record_type="action_link",
                path="registry/action-links.yaml",
                title=label,
                summary=f"Approved Urbancrest action link for {', '.join(intents)}.",
                content=f"Label: {label}\nURL: {link.get('url', '')}\nIntents: {', '.join(intents)}",
                priority=int(link.get("priority") or 50),
                category=["action_link"],
                intents=intents,
                tags=["action", "link", *intents],
                search_terms=[label, *intents],
                action_key=key,
                url=link.get("url"),
                external=link.get("external", False),
                church_center_modal=link.get("church_center_modal", False),
            )
        )
    return records


def relationship_records() -> list[dict[str, Any]]:
    data = yaml.safe_load((ROOT / "relationships/ministry-staff.yaml").read_text(encoding="utf-8")) or {}
    records: list[dict[str, Any]] = []
    for relationship in data.get("relationships", []):
        ministry = str(relationship.get("ministry") or "")
        primary = str(relationship.get("primary_staff_key") or "")
        recommended = str(relationship.get("recommended_contact_staff_key") or "")
        selected_staff_key = primary or recommended
        related = as_list(relationship.get("related_staff_keys"))
        leadership_status = str(relationship.get("leadership_status") or "staffed")
        open_role = str(relationship.get("open_role") or "")
        answer_guidance = str(relationship.get("answer_guidance") or "")
        routing_aliases = as_list(relationship.get("routing_aliases"))
        routing_topics = as_list(relationship.get("routing_topics"))
        relationship_label = str(relationship.get("relationship_label") or relationship.get("label") or "")

        summary_parts = [f"Staff relationship for {ministry.replace('_', ' ')}."]
        if open_role:
            summary_parts.append(f"Open role: {open_role}.")
        if selected_staff_key:
            summary_parts.append(f"Recommended staff key: {selected_staff_key}.")
        summary = " ".join(summary_parts)

        content_lines = [
            f"Ministry: {ministry}",
            f"Leadership status: {leadership_status}",
            f"Primary staff key: {primary or 'none'}",
            f"Recommended contact staff key: {recommended or 'none'}",
            f"Related staff keys: {', '.join(related)}",
        ]
        if open_role:
            content_lines.append(f"Open role: {open_role}")
        if routing_aliases:
            content_lines.append(f"Routing aliases: {', '.join(routing_aliases)}")
        if routing_topics:
            content_lines.append(f"Routing topics: {', '.join(routing_topics)}")
        if answer_guidance:
            content_lines.append(f"Answer guidance: {answer_guidance}")

        records.append(
            record_base(
                record_id=f"relationship.ministry_staff.{ministry}",
                record_type="relationship",
                path="relationships/ministry-staff.yaml",
                title=f"{ministry.replace('_', ' ').title()} staff relationship",
                summary=summary,
                content="\n".join(content_lines),
                priority=95 if leadership_status in {"vacant", "transitional"} else 85,
                category=["relationship", "staff"],
                intents=["ministry_contact", "staff_routing", "missions_leadership"],
                tags=[ministry, "staff", "ministry", leadership_status, *routing_topics],
                search_terms=[
                    ministry.replace("_", " "),
                    f"who oversees {ministry.replace('_', ' ')}",
                    f"who leads {ministry.replace('_', ' ')}",
                    f"who do I contact about {ministry.replace('_', ' ')}",
                    open_role,
                    *routing_aliases,
                    *routing_topics,
                ],
                ministries=[ministry],
                ministry=ministry,
                routing_aliases=routing_aliases,
                routing_topics=routing_topics,
                relationship_label=relationship_label,
                staff_key=selected_staff_key,
                primary_staff_key=primary,
                recommended_contact_staff_key=recommended,
                related_staff_keys=related,
                leadership_status=leadership_status,
                open_role=open_role,
                answer_guidance=answer_guidance,
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



def live_freshness_metadata() -> dict[str, dict[str, Any]]:
    runtime_sources_path = ROOT / "registry/runtime-sources.yaml"
    runtime_sources = yaml.safe_load(runtime_sources_path.read_text(encoding="utf-8")) or {}
    policies = runtime_sources.get("freshness") or {}
    if not isinstance(policies, dict):
        raise ValueError("registry/runtime-sources.yaml freshness must be an object")

    required_keys = ("calendar", "small_groups")
    result: dict[str, dict[str, Any]] = {}
    for key in required_keys:
        policy = policies.get(key)
        if not isinstance(policy, dict):
            raise ValueError(f"registry/runtime-sources.yaml freshness.{key} is missing")

        heartbeat_path = str(policy.get("heartbeat_path") or "").strip()
        heartbeat_field = str(policy.get("heartbeat_field") or "generated_at").strip()
        fallback_action_key = str(policy.get("fallback_action_key") or "").strip()
        stale_behavior = str(policy.get("stale_behavior") or "").strip()
        max_age_hours = policy.get("max_age_hours")

        if not heartbeat_path:
            raise ValueError(f"freshness.{key}.heartbeat_path is required")
        source_path = ROOT / heartbeat_path
        if not source_path.is_file():
            raise ValueError(f"freshness.{key} heartbeat source does not exist: {heartbeat_path}")

        source_data = yaml.safe_load(source_path.read_text(encoding="utf-8")) or {}
        generated_at = str(source_data.get(heartbeat_field) or "").strip()
        if not generated_at:
            raise ValueError(
                f"freshness.{key} source {heartbeat_path} has no {heartbeat_field} value"
            )

        try:
            numeric_max_age = float(max_age_hours)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"freshness.{key}.max_age_hours must be numeric") from exc
        if numeric_max_age <= 0:
            raise ValueError(f"freshness.{key}.max_age_hours must be positive")

        result[key] = {
            "generated_at": generated_at,
            "max_age_hours": int(numeric_max_age) if numeric_max_age.is_integer() else numeric_max_age,
            "source_path": heartbeat_path,
            "heartbeat_field": heartbeat_field,
            "fallback_action_key": fallback_action_key,
            "stale_behavior": stale_behavior,
        }

    return result


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

    by_id: dict[str, dict[str, Any]] = {}
    duplicate_details: list[str] = []
    for record in records:
        record_id = str(record.get("id") or "").strip()
        if not record_id:
            raise ValueError(f"Search-index record from {record.get('path', 'unknown source')} has no id")
        previous = by_id.get(record_id)
        if previous is not None:
            duplicate_details.append(
                f"{record_id}: {previous.get('path', 'unknown source')} <-> {record.get('path', 'unknown source')}"
            )
        else:
            by_id[record_id] = record

    if duplicate_details:
        details = "\n  - ".join(duplicate_details)
        raise ValueError(f"Duplicate search-index record IDs detected:\n  - {details}")

    records = sorted(
        records,
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
        "freshness": live_freshness_metadata(),
        "records": records,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(records)} retrieval records to {OUTPUT.relative_to(ROOT)}.")


if __name__ == "__main__":
    main()
