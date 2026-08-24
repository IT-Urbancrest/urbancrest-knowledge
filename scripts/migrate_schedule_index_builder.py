#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

PATH = Path(__file__).resolve().parent / "build_search_index.py"
START_MARKER = "def schedule_records() -> list[dict[str, Any]]:\n"
END_MARKER = "\n\ndef event_records() -> list[dict[str, Any]]:\n"
MIGRATED_MARKER = "# schedule schema 2.1 compiler"

NEW_FUNCTION = r'''def schedule_records() -> list[dict[str, Any]]:
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
'''


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    if MIGRATED_MARKER in text:
        print("schedule_records() already uses schema 2.1; no migration needed.")
        return

    start = text.find(START_MARKER)
    if start < 0:
        raise RuntimeError("Could not find schedule_records() in build_search_index.py")
    end = text.find(END_MARKER, start)
    if end < 0:
        raise RuntimeError("Could not find event_records() boundary in build_search_index.py")

    current = text[start:end]
    if "data.get(\"schedule\", {}).get(\"weekly\", {})" not in current:
        raise RuntimeError("schedule_records() is not the expected legacy implementation; refusing partial migration")

    updated = text[:start] + NEW_FUNCTION + text[end:]
    PATH.write_text(updated, encoding="utf-8")
    print("Migrated schedule_records() to registry/schedule.yaml schema 2.1.")


if __name__ == "__main__":
    main()
