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
        return "\n".join(
            f"{key}: {flatten_text(item)}"
            for key, item in value.items()
        )

    if isinstance(value, list):
        return "\n".join(
            flatten_text(item)
            for item in value
        )

    return str(value)


def truncate(value: str, limit: int = 2400) -> str:
    value = value.strip()

    return (
        value
        if len(value) <= limit
        else value[: limit - 3].rstrip() + "..."
    )


def event_activity_aliases(title: str) -> list[str]:
    """Create public-facing activity aliases from a calendar event title."""

    cleaned = re.sub(
        r"\s+",
        " ",
        str(title or ""),
    ).strip()

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
        candidate = re.sub(
            pattern,
            "",
            simplified,
            flags=re.IGNORECASE,
        ).strip()

        if (
            candidate
            and candidate.casefold() != simplified.casefold()
        ):
            aliases.append(candidate)
            simplified = candidate

    # Add a spaced variant for common compound activity names.
    for alias in list(aliases):
        match = re.search(
            r"\bpickleball\b",
            alias,
            flags=re.IGNORECASE,
        )

        if match:
            replacement = (
                "Pickle ball"
                if match.group(0)[:1].isupper()
                else "pickle ball"
            )

            spaced = (
                alias[: match.start()]
                + replacement
                + alias[match.end() :]
            )

            if spaced.casefold() != alias.casefold():
                aliases.append(spaced)

    return unique(aliases)


def parse_markdown(
    path: Path,
) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")

    if not text.startswith("---\n"):
        return {}, text.strip()

    parts = text.split("---\n", 2)

    if len(parts) < 3:
        return {}, text.strip()

    metadata = yaml.safe_load(parts[1]) or {}

    return (
        metadata if isinstance(metadata, dict) else {},
        parts[2].strip(),
    )


def intent_values(
    metadata: dict[str, Any],
) -> list[str]:
    intent = metadata.get("intent")

    if isinstance(intent, dict):
        return unique(
            as_list(intent.get("primary"))
            + as_list(intent.get("secondary"))
        )

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
        if (
            value is not None
            and value != []
            and value != ""
        ):
            record[key] = value

    return record


def markdown_record_type(
    relative: str,
    metadata: dict[str, Any],
) -> str:
    """
    Determine the search-index record type for a Markdown file.

    Explicit record_type frontmatter wins when present. Sermon files
    historically rely on their directory structure instead.
    """

    explicit = str(
        metadata.get("record_type") or ""
    ).strip()

    if explicit:
        return explicit

    if relative.startswith(
        "knowledge/sermons/series/"
    ):
        return "sermon_series"

    if relative.startswith(
        "knowledge/sermons/"
    ):
        return "sermon"

    return "knowledge"


def markdown_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    # Parse the Markdown files first so we can resolve sermon
    # series titles before building individual sermon records.
    sources: list[
        tuple[
            Path,
            str,
            dict[str, Any],
            str,
        ]
    ] = []

    for path in sorted(
        (ROOT / "knowledge").rglob("*.md")
    ):
        relative = (
            path.relative_to(ROOT).as_posix()
        )

        if relative in SKIP_MARKDOWN:
            continue

        if relative.startswith(
            "knowledge/events/generated/"
        ):
            continue

        if relative.startswith(
            "knowledge/small-groups/generated/"
        ):
            continue

        metadata, body = parse_markdown(path)

        status = str(
            metadata.get(
                "status",
                "published",
            )
        )

        if status not in {
            "published",
            "active",
        }:
            continue

        sources.append(
            (
                path,
                relative,
                metadata,
                body,
            )
        )

    # Build series_id -> series title lookup so individual
    # sermon records can expose the human-readable series title.
    series_titles: dict[str, str] = {}

    for (
        path,
        relative,
        metadata,
        body,
    ) in sources:
        record_type = markdown_record_type(
            relative,
            metadata,
        )

        if record_type != "sermon_series":
            continue

        series_id = str(
            metadata.get("series_id") or ""
        ).strip()

        title = str(
            metadata.get("title")
            or path.stem.replace(
                "-",
                " ",
            ).title()
        )

        if series_id:
            series_titles[series_id] = title

    for (
        path,
        relative,
        metadata,
        body,
    ) in sources:
        title = str(
            metadata.get("title")
            or path.stem.replace(
                "-",
                " ",
            ).title()
        )

        status = str(
            metadata.get(
                "status",
                "published",
            )
        )

        # Preserve authored record_type if one exists.
        # Otherwise infer sermons from the sermon directory.
        record_type = markdown_record_type(
            relative,
            metadata,
        )

        category = as_list(
            metadata.get("category")
        )

        intents = intent_values(metadata)

        tags = as_list(
            metadata.get("tags")
        )

        search_terms = as_list(
            metadata.get("search_terms")
        )

        topics = as_list(
            metadata.get("topics")
        )

        extra: dict[str, Any] = {
            "status": status,
            "staff_key": metadata.get(
                "staff_key"
            ),
            "recommended_contact_staff_key":
                metadata.get(
                    "recommended_contact_staff_key"
                ),
            "related_staff_keys": as_list(
                metadata.get(
                    "related_staff_keys"
                )
            ),
            "leadership_status": metadata.get(
                "leadership_status"
            ),
            "open_role": metadata.get(
                "open_role"
            ),
            "review_trigger": metadata.get(
                "review_trigger"
            ),
            "answer_guidance": metadata.get(
                "answer_guidance"
            ),
            "confidence": metadata.get(
                "confidence"
            ),
            "authoritative": metadata.get(
                "authoritative"
            ),
            "authoritative_for": as_list(
                metadata.get(
                    "authoritative_for"
                )
            ),
        }

        # Preserve sermon-specific structured metadata.
        if record_type == "sermon":
            sermon_date = (
                metadata.get("sermon_date")
                or metadata.get("date")
            )

            series_id = str(
                metadata.get("series_id")
                or ""
            ).strip()

            series_title = (
                metadata.get("series_title")
                or series_titles.get(
                    series_id
                )
            )

            # Topics are useful retrieval signals for
            # questions such as:
            # "What sermon talked about generosity?"
            tags = unique(
                [
                    *tags,
                    "sermon",
                    *topics,
                ]
            )

            search_terms = unique(
                [
                    *search_terms,
                    *topics,
                ]
            )

            if "sermon" not in intents:
                intents.append("sermon")

            extra.update(
                {
                    # Retrieval expects sermon_date even
                    # though the Markdown sermon schema
                    # historically uses "date".
                    "sermon_date": (
                        str(sermon_date)
                        if sermon_date is not None
                        else None
                    ),
                    "date": (
                        str(sermon_date)
                        if sermon_date is not None
                        else None
                    ),
                    "speaker": metadata.get(
                        "speaker"
                    ),
                    "series_id": (
                        series_id
                        or None
                    ),
                    "series_title":
                        series_title,
                    "primary_scripture":
                        metadata.get(
                            "primary_scripture"
                        ),
                    "notes_url":
                        metadata.get(
                            "notes_url"
                        ),
                    "topics": topics,
                    "title_source":
                        metadata.get(
                            "title_source"
                        ),
                    "outline_source":
                        metadata.get(
                            "outline_source"
                        ),
                    "summary_source":
                        metadata.get(
                            "summary_source"
                        ),
                }
            )

        # Preserve sermon-series structured metadata.
        elif record_type == "sermon_series":
            series_id = str(
                metadata.get("series_id")
                or ""
            ).strip()

            raw_sermons = metadata.get(
                "sermons"
            )

            normalized_sermons: list[
                dict[str, Any]
            ] = []

            if isinstance(
                raw_sermons,
                list,
            ):
                for sermon in raw_sermons:
                    if not isinstance(
                        sermon,
                        dict,
                    ):
                        continue

                    normalized_sermons.append(
                        {
                            "date": (
                                str(
                                    sermon.get(
                                        "date"
                                    )
                                )
                                if sermon.get(
                                    "date"
                                )
                                is not None
                                else ""
                            ),
                            "title": str(
                                sermon.get(
                                    "title"
                                )
                                or ""
                            ),
                            "speaker": str(
                                sermon.get(
                                    "speaker"
                                )
                                or ""
                            ),
                            "primary_scripture":
                                str(
                                    sermon.get(
                                        "primary_scripture"
                                    )
                                    or ""
                                ),
                        }
                    )

            tags = unique(
                [
                    *tags,
                    "sermon",
                    "sermon series",
                ]
            )

            if (
                "sermon_series"
                not in intents
            ):
                intents.append(
                    "sermon_series"
                )

            extra.update(
                {
                    "series_id": (
                        series_id
                        or None
                    ),
                    "series_status":
                        metadata.get(
                            "series_status"
                        ),
                    "start_date": (
                        str(
                            metadata.get(
                                "start_date"
                            )
                        )
                        if metadata.get(
                            "start_date"
                        )
                        is not None
                        else None
                    ),
                    "end_date": (
                        str(
                            metadata.get(
                                "end_date"
                            )
                        )
                        if metadata.get(
                            "end_date"
                        )
                        is not None
                        else None
                    ),
                    "primary_scripture":
                        metadata.get(
                            "primary_scripture"
                        ),
                    "sermons":
                        normalized_sermons,
                    "artwork_url":
                        metadata.get(
                            "artwork_url"
                        ),
                    "image_url":
                        metadata.get(
                            "image_url"
                        ),
                    "series_artwork_url":
                        metadata.get(
                            "series_artwork_url"
                        ),
                }
            )

        records.append(
            record_base(
                record_id=str(
                    metadata.get("id")
                    or relative
                ),
                record_type=record_type,
                path=relative,
                title=title,
                summary=str(
                    metadata.get("summary")
                    or ""
                ),
                content=body,
                priority=int(
                    metadata.get("priority")
                    or 50
                ),
                category=category,
                intents=intents,
                tags=tags,
                search_terms=search_terms,
                ministries=as_list(
                    metadata.get(
                        "ministries"
                    )
                ),
                audiences=as_list(
                    metadata.get(
                        "audience"
                    )
                ),
                resources=as_list(
                    metadata.get(
                        "resources"
                    )
                ),
                **extra,
            )
        )

    return records


def schedule_records() -> list[dict[str, Any]]:
    path = ROOT / "registry/schedule.yaml"

    data = yaml.safe_load(
        path.read_text(
            encoding="utf-8"
        )
    ) or {}

    weekly = (
        data.get(
            "schedule",
            {},
        ).get(
            "weekly",
            {},
        )
    )

    sunday_times = (
        weekly.get(
            "sunday",
            {},
        ).get(
            "worship",
            [],
        )
    )

    wednesday = weekly.get(
        "wednesday",
        {},
    )

    content_lines = [
        "Regular weekly schedule:",
        (
            "Sunday worship: "
            + ", ".join(
                str(value)
                for value in sunday_times
            )
        ),
    ]

    for key, item in wednesday.items():
        if not isinstance(
            item,
            dict,
        ):
            continue

        label = (
            key.replace(
                "_",
                " ",
            ).title()
        )

        time = str(
            item.get("time")
            or ""
        )

        location = str(
            item.get("location")
            or ""
        )

        line = (
            f"Wednesday {label}: {time}"
        )

        if location:
            line += f" at {location}"

        content_lines.append(line)

    return [
        record_base(
            record_id="schedule.weekly",
            record_type="schedule",
            path="registry/schedule.yaml",
            title=(
                "Urbancrest Weekly "
                "Service Schedule"
            ),
            summary=(
                "Sunday worship services "
                "are at 9:30 AM and 11:00 AM."
            ),
            content="\n".join(
                content_lines
            ),
            priority=int(
                data.get("priority")
                or 120
            ),
            category=[
                "schedule",
                "about",
            ],
            intents=[
                "service_times",
                "sunday_service_times",
                "weekly_schedule",
                "visit",
            ],
            tags=[
                "service times",
                "Sunday services",
                "Sunday worship",
                "weekly schedule",
            ],
            search_terms=[
                "What time are Sunday services?",
                "What are your Sunday service times?",
                "When are Sunday services?",
                "What time does church start?",
                "What time is church?",
                "When does Urbancrest meet?",
                "Sunday worship times",
                "Sunday service times",
            ],
            authoritative=bool(
                data.get(
                    "authoritative",
                    True,
                )
            ),
            authoritative_for=as_list(
                data.get(
                    "source_of_truth_for"
                )
            ),
            confidence="high",
            answer_guidance=data.get(
                "answer_guidance"
            ),
            sunday_service_times=as_list(
                sunday_times
            ),
            timezone=data.get(
                "timezone",
                "America/New_York",
            ),
        )
    ]


def event_records() -> list[dict[str, Any]]:
    path = (
        ROOT
        / "registry/events-live.yaml"
    )

    data = yaml.safe_load(
        path.read_text(
            encoding="utf-8"
        )
    ) or {}

    records: list[
        dict[str, Any]
    ] = []

    for event in data.get(
        "events",
        [],
    ):
        event_id = str(
            event.get("id")
            or ""
        )

        title = str(
            event.get("title")
            or "Untitled Event"
        )

        description = str(
            event.get("description")
            or ""
        )

        details = str(
            event.get("details")
            or ""
        )

        content = "\n\n".join(
            value
            for value in (
                description,
                (
                    f"Details:\n{details}"
                    if details
                    else ""
                ),
            )
            if value
        )

        activity_aliases = (
            event_activity_aliases(
                title
            )
        )

        normalized_title = (
            title.casefold()
        )

        routine_service_occurrence = (
            "sunday morning services"
            in normalized_title
            or
            "sunday worship service"
            in normalized_title
        )

        event_priority = int(
            event.get(
                "event_priority"
            )
            or 50
        )

        if routine_service_occurrence:
            event_priority = min(
                event_priority,
                20,
            )

        records.append(
            record_base(
                record_id=(
                    f"events.live."
                    f"{event_id}"
                ),
                record_type="event",
                path=str(
                    event.get(
                        "knowledge_file"
                    )
                    or
                    "registry/events-live.yaml"
                ),
                title=title,
                summary=str(
                    event.get("summary")
                    or ""
                ),
                content=content,
                priority=event_priority,
                category=[
                    "events",
                    str(
                        event.get(
                            "event_category"
                        )
                        or
                        "general_event"
                    ),
                ],
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
                    str(
                        event.get(
                            "event_category"
                        )
                        or
                        "general_event"
                    ),
                    *activity_aliases,
                ],
                search_terms=unique(
                    [
                        title,
                        f"When is {title}?",
                        f"Tell me about {title}",
                        (
                            "What are the details "
                            f"for {title}?"
                        ),
                        (
                            "What is the menu for "
                            f"{title}?"
                        ),
                        (
                            "How do I register for "
                            f"{title}?"
                        ),
                    ]
                    + [
                        phrase
                        for alias
                        in activity_aliases
                        for phrase
                        in (
                            alias,
                            (
                                "Does Urbancrest have "
                                f"{alias}?"
                            ),
                            (
                                "Does Urbancrest offer "
                                f"{alias}?"
                            ),
                            f"Do you have {alias}?",
                            f"Do you offer {alias}?",
                            (
                                f"Is there {alias} "
                                "at Urbancrest?"
                            ),
                            (
                                "Can I participate in "
                                f"{alias}?"
                            ),
                            (
                                f"Can I play {alias} "
                                "at Urbancrest?"
                            ),
                        )
                    ]
                ),
                ministries=as_list(
                    event.get(
                        "ministries"
                    )
                ),
                audiences=as_list(
                    event.get(
                        "audiences"
                    )
                ),
                event_id=event_id,
                activity_aliases=
                    activity_aliases,
                event_category=event.get(
                    "event_category"
                ),
                event_start=event.get(
                    "start"
                ),
                event_end=event.get(
                    "end"
                ),
                sort_start_utc=event.get(
                    "sort_start_utc"
                ),
                sort_end_utc=event.get(
                    "sort_end_utc"
                ),
                location=event.get(
                    "location"
                ),
                details=event.get(
                    "details"
                ),
                details_source=event.get(
                    "details_source"
                ),
                planning_center_event_id=
                    event.get(
                        "planning_center_event_id"
                    ),
                planning_center_event_instance_id=
                    event.get(
                        "planning_center_event_instance_id"
                    ),
                planning_center_event_time_id=
                    event.get(
                        "planning_center_event_time_id"
                    ),
                registration_url=
                    event.get(
                        "registration_url"
                    ),
                info_url=event.get(
                    "info_url"
                ),
                image_url=event.get(
                    "image_url"
                ),
                knowledge_file=
                    event.get(
                        "knowledge_file"
                    ),
                chronological_rank=
                    event.get(
                        "chronological_rank"
                    ),
                routine_schedule_occurrence=
                    routine_service_occurrence,
                retrieval_exclude_for_intents=(
                    [
                        "service_times",
                        "sunday_service_times",
                        "weekly_schedule",
                    ]
                    if routine_service_occurrence
                    else []
                ),
            )
        )

    return records


def group_records() -> list[dict[str, Any]]:
    path = (
        ROOT
        / "registry/small-groups-live.yaml"
    )

    data = yaml.safe_load(
        path.read_text(
            encoding="utf-8"
        )
    ) or {}

    records: list[
        dict[str, Any]
    ] = []

    for group in data.get(
        "groups",
        [],
    ):
        group_id = str(
            group.get("id")
            or ""
        )

        title = str(
            group.get("title")
            or "Untitled Small Group"
        )

        meetings = (
            group.get(
                "future_meetings"
            )
            or []
        )

        schedule_lines = [
            str(
                item.get(
                    "display_when"
                )
                or item.get("start")
                or ""
            )
            for item in meetings
            if isinstance(
                item,
                dict,
            )
        ]

        content = "\n\n".join(
            filter(
                None,
                [
                    str(
                        group.get(
                            "description"
                        )
                        or ""
                    ),
                    (
                        f"Details:\n"
                        f"{group.get('details')}"
                        if group.get(
                            "details"
                        )
                        else ""
                    ),
                    (
                        "Upcoming meetings:\n"
                        + "\n".join(
                            schedule_lines
                        )
                    ),
                ],
            )
        )

        next_meeting = (
            group.get(
                "next_meeting"
            )
            or {}
        )

        records.append(
            record_base(
                record_id=(
                    "small_groups.live."
                    f"{group_id}"
                ),
                record_type=
                    "small_group",
                path=str(
                    group.get(
                        "knowledge_file"
                    )
                    or
                    "registry/small-groups-live.yaml"
                ),
                title=title,
                summary=str(
                    group.get("summary")
                    or ""
                ),
                content=content,
                priority=int(
                    group.get(
                        "event_priority"
                    )
                    or 20
                ),
                category=[
                    "small_groups"
                ],
                intents=[
                    "small_groups",
                    "small_group_details",
                    "next_small_group_meeting",
                    "group_schedule",
                ],
                tags=[
                    "small_group",
                    "groups",
                    "calendar",
                    "recurring",
                ],
                search_terms=[
                    title,
                    (
                        f"When does "
                        f"{title} meet?"
                    ),
                    (
                        f"Tell me about "
                        f"{title}"
                    ),
                ],
                ministries=as_list(
                    group.get(
                        "ministries"
                    )
                ),
                audiences=as_list(
                    group.get(
                        "audiences"
                    )
                ),
                group_id=group_id,
                next_meeting=
                    next_meeting,
                future_meetings=
                    meetings,
                sort_start_utc=(
                    next_meeting.get(
                        "sort_start_utc"
                    )
                    if isinstance(
                        next_meeting,
                        dict,
                    )
                    else None
                ),
                sort_end_utc=(
                    next_meeting.get(
                        "sort_end_utc"
                    )
                    if isinstance(
                        next_meeting,
                        dict,
                    )
                    else None
                ),
                location=group.get(
                    "location"
                ),
                details=group.get(
                    "details"
                ),
                details_source=
                    group.get(
                        "details_source"
                    ),
                planning_center_event_id=
                    group.get(
                        "planning_center_event_id"
                    ),
                planning_center_event_instance_id=
                    group.get(
                        "planning_center_event_instance_id"
                    ),
                planning_center_event_time_id=
                    group.get(
                        "planning_center_event_time_id"
                    ),
                registration_url=
                    group.get(
                        "registration_url"
                    ),
                info_url=group.get(
                    "info_url"
                ),
                knowledge_file=
                    group.get(
                        "knowledge_file"
                    ),
            )
        )

    return records


def staff_records() -> list[dict[str, Any]]:
    staff_data = yaml.safe_load(
        (
            ROOT
            / "registry/staff.yaml"
        ).read_text(
            encoding="utf-8"
        )
    ) or {}

    route_data = yaml.safe_load(
        (
            ROOT
            / "registry/staff-routing.yaml"
        ).read_text(
            encoding="utf-8"
        )
    ) or {}

    directory = staff_data.get(
        "staff",
        {},
    )

    routing = route_data.get(
        "routing",
        {},
    )

    records: list[
        dict[str, Any]
    ] = []

    for key, person in directory.items():
        route = routing.get(
            key,
            {},
        )

        name = str(
            person.get("name")
            or key
        )

        role = str(
            person.get("role")
            or "Staff"
        )

        aliases = as_list(
            route.get("aliases")
        )

        topics = as_list(
            route.get("topics")
        )

        ministries = as_list(
            route.get("ministries")
        )

        answer_guidance = str(
            route.get(
                "answer_guidance"
            )
            or ""
        )

        staff_content = (
            f"Display name: "
            f"{person.get('display_name', name)}\n"
            f"Role: {role}\n"
            f"Ministries: "
            f"{', '.join(ministries)}\n"
            f"Topics: "
            f"{', '.join(topics)}"
        )

        if answer_guidance:
            staff_content += (
                "\nAnswer guidance: "
                + answer_guidance
            )

        records.append(
            record_base(
                record_id=f"staff.{key}",
                record_type=
                    "staff_route",
                path=(
                    "registry/"
                    "staff-routing.yaml"
                ),
                title=name,
                summary=(
                    f"{name} serves as "
                    f"{role}. Full biography "
                    "and fun facts are loaded "
                    "from Base44 Staff when "
                    "relevant."
                ),
                content=staff_content,
                priority=90,
                category=["staff"],
                intents=[
                    "staff",
                    "staff_details",
                    "staff_routing",
                    "ministry_contact",
                ],
                tags=[
                    "staff",
                    role,
                    *ministries,
                ],
                search_terms=[
                    name,
                    str(
                        person.get(
                            "display_name"
                        )
                        or ""
                    ),
                    role,
                    *aliases,
                    *topics,
                ],
                ministries=ministries,
                staff_key=key,
                display_name=
                    person.get(
                        "display_name"
                    ),
                role=role,
                pastoral_staff=
                    person.get(
                        "pastoral_staff",
                        False,
                    ),
                show_card=
                    route.get(
                        "show_card",
                        True,
                    ),
                profile_source=
                    "base44.Staff",
                answer_guidance=
                    answer_guidance,
            )
        )

    return records


def action_link_records() -> list[dict[str, Any]]:
    data = yaml.safe_load(
        (
            ROOT
            / "registry/action-links.yaml"
        ).read_text(
            encoding="utf-8"
        )
    ) or {}

    records: list[
        dict[str, Any]
    ] = []

    for key, link in data.get(
        "links",
        {},
    ).items():
        label = str(
            link.get("label")
            or key
        )

        intents = as_list(
            link.get("intents")
        )

        records.append(
            record_base(
                record_id=(
                    f"action_link.{key}"
                ),
                record_type=
                    "action_link",
                path=(
                    "registry/"
                    "action-links.yaml"
                ),
                title=label,
                summary=(
                    "Approved Urbancrest "
                    "action link for "
                    f"{', '.join(intents)}."
                ),
                content=(
                    f"Label: {label}\n"
                    f"URL: "
                    f"{link.get('url', '')}\n"
                    f"Intents: "
                    f"{', '.join(intents)}"
                ),
                priority=int(
                    link.get(
                        "priority"
                    )
                    or 50
                ),
                category=[
                    "action_link"
                ],
                intents=intents,
                tags=[
                    "action",
                    "link",
                    *intents,
                ],
                search_terms=[
                    label,
                    *intents,
                ],
                action_key=key,
                url=link.get("url"),
                external=link.get(
                    "external",
                    False,
                ),
                church_center_modal=
                    link.get(
                        "church_center_modal",
                        False,
                    ),
            )
        )

    return records


def relationship_records() -> list[dict[str, Any]]:
    data = yaml.safe_load(
        (
            ROOT
            / "relationships/ministry-staff.yaml"
        ).read_text(
            encoding="utf-8"
        )
    ) or {}

    records: list[
        dict[str, Any]
    ] = []

    for relationship in data.get(
        "relationships",
        [],
    ):
        ministry = str(
            relationship.get(
                "ministry"
            )
            or ""
        )

        primary = str(
            relationship.get(
                "primary_staff_key"
            )
            or ""
        )

        recommended = str(
            relationship.get(
                "recommended_contact_staff_key"
            )
            or ""
        )

        selected_staff_key = (
            primary
            or recommended
        )

        related = as_list(
            relationship.get(
                "related_staff_keys"
            )
        )

        leadership_status = str(
            relationship.get(
                "leadership_status"
            )
            or "staffed"
        )

        open_role = str(
            relationship.get(
                "open_role"
            )
            or ""
        )

        answer_guidance = str(
            relationship.get(
                "answer_guidance"
            )
            or ""
        )

        summary_parts = [
            (
                "Staff relationship for "
                f"{ministry.replace('_', ' ')}."
            )
        ]

        if open_role:
            summary_parts.append(
                f"Open role: {open_role}."
            )

        if selected_staff_key:
            summary_parts.append(
                "Recommended staff key: "
                f"{selected_staff_key}."
            )

        summary = " ".join(
            summary_parts
        )

        content_lines = [
            f"Ministry: {ministry}",
            (
                "Leadership status: "
                f"{leadership_status}"
            ),
            (
                "Primary staff key: "
                f"{primary or 'none'}"
            ),
            (
                "Recommended contact "
                "staff key: "
                f"{recommended or 'none'}"
            ),
            (
                "Related staff keys: "
                f"{', '.join(related)}"
            ),
        ]

        if open_role:
            content_lines.append(
                f"Open role: {open_role}"
            )

        if answer_guidance:
            content_lines.append(
                "Answer guidance: "
                f"{answer_guidance}"
            )

        records.append(
            record_base(
                record_id=(
                    "relationship."
                    "ministry_staff."
                    f"{ministry}"
                ),
                record_type=
                    "relationship",
                path=(
                    "relationships/"
                    "ministry-staff.yaml"
                ),
                title=(
                    f"{ministry.replace('_', ' ').title()} "
                    "staff relationship"
                ),
                summary=summary,
                content="\n".join(
                    content_lines
                ),
                priority=(
                    95
                    if leadership_status
                    in {
                        "vacant",
                        "transitional",
                    }
                    else 85
                ),
                category=[
                    "relationship",
                    "staff",
                ],
                intents=[
                    "ministry_contact",
                    "staff_routing",
                    "missions_leadership",
                ],
                tags=[
                    ministry,
                    "staff",
                    "ministry",
                    leadership_status,
                ],
                search_terms=[
                    ministry.replace(
                        "_",
                        " ",
                    ),
                    (
                        "who oversees "
                        f"{ministry.replace('_', ' ')}"
                    ),
                    (
                        "who leads "
                        f"{ministry.replace('_', ' ')}"
                    ),
                    (
                        "who do I contact about "
                        f"{ministry.replace('_', ' ')}"
                    ),
                    open_role,
                ],
                ministries=[
                    ministry
                ],
                staff_key=
                    selected_staff_key,
                primary_staff_key=
                    primary,
                recommended_contact_staff_key=
                    recommended,
                related_staff_keys=
                    related,
                leadership_status=
                    leadership_status,
                open_role=open_role,
                answer_guidance=
                    answer_guidance,
            )
        )

    return records


def generic_yaml_records() -> list[dict[str, Any]]:
    records: list[
        dict[str, Any]
    ] = []

    for root_name in (
        "registry",
        "relationships",
        "intents",
    ):
        for path in sorted(
            (ROOT / root_name).glob(
                "*.yaml"
            )
        ):
            relative = (
                path.relative_to(
                    ROOT
                ).as_posix()
            )

            if relative in SKIP_YAML:
                continue

            data = yaml.safe_load(
                path.read_text(
                    encoding="utf-8"
                )
            )

            if data is None:
                continue

            title = (
                path.stem
                .replace("-", " ")
                .replace("_", " ")
                .title()
            )

            records.append(
                record_base(
                    record_id=(
                        f"file.{relative}"
                    ),
                    record_type=(
                        "routing"
                        if root_name
                        == "intents"
                        else "registry"
                    ),
                    path=relative,
                    title=title,
                    summary=(
                        f"Structured "
                        f"{root_name} data "
                        f"from {relative}."
                    ),
                    content=flatten_text(
                        data
                    ),
                    priority=(
                        65
                        if root_name
                        == "intents"
                        else 60
                    ),
                    category=[
                        root_name
                    ],
                    intents=(
                        [path.stem]
                        if root_name
                        == "intents"
                        else []
                    ),
                    tags=[
                        root_name,
                        path.stem,
                    ],
                    search_terms=[
                        title,
                        path.stem.replace(
                            "-",
                            " ",
                        ),
                    ],
                )
            )

    return records


def main() -> None:
    records = []

    records.extend(
        markdown_records()
    )

    records.extend(
        schedule_records()
    )

    records.extend(
        event_records()
    )

    records.extend(
        group_records()
    )

    records.extend(
        staff_records()
    )

    records.extend(
        action_link_records()
    )

    records.extend(
        relationship_records()
    )

    records.extend(
        generic_yaml_records()
    )

    deduped: dict[
        str,
        dict[str, Any],
    ] = {}

    for record in records:
        deduped[
            record["id"]
        ] = record

    records = sorted(
        deduped.values(),
        key=lambda item: (
            -int(
                item.get(
                    "priority",
                    0,
                )
            ),
            item.get(
                "record_type",
                "",
            ),
            item.get(
                "title",
                "",
            ).casefold(),
        ),
    )

    manifest = yaml.safe_load(
        (
            ROOT
            / "manifest.yaml"
        ).read_text(
            encoding="utf-8"
        )
    ) or {}

    payload = {
        "schema_version": "1.0",
        "repository": manifest.get(
            "repository",
            "urbancrest-knowledge",
        ),
        "repository_version":
            manifest.get(
                "version"
            ),
        "generated_at":
            datetime.now(
                timezone.utc
            ).isoformat().replace(
                "+00:00",
                "Z",
            ),
        "timezone":
            "America/New_York",
        "record_count":
            len(records),
        "config": {
            "personality": (
                ROOT
                / "AI_PERSONALITY.md"
            ).read_text(
                encoding="utf-8"
            ),
            "style_guide": (
                ROOT
                / "STYLE_GUIDE.md"
            ).read_text(
                encoding="utf-8"
            ),
            "max_retrieval_records":
                8,
            "staff_profile_source":
                "base44.Staff",
            "admin_knowledge_source":
                "base44.KnowledgeEntry",
        },
        "source_rules":
            yaml.safe_load(
                (
                    ROOT
                    / "registry/runtime-sources.yaml"
                ).read_text(
                    encoding="utf-8"
                )
            ),
        "records": records,
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"Wrote {len(records)} "
        "retrieval records to "
        f"{OUTPUT.relative_to(ROOT)}."
    )


if __name__ == "__main__":
    main()
