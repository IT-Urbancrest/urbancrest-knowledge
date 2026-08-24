#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

BUILD_PATH = Path("scripts/build_search_index.py")
REG_PATH = Path("scripts/sync_registrations.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    build = BUILD_PATH.read_text(encoding="utf-8")
    registrations = REG_PATH.read_text(encoding="utf-8")

    if "registration_available=bool(event.get(\"registration_available\"" in build:
        print("Runtime event fields are already present in build_search_index.py; no changes needed.")
        return

    build = replace_once(
        build,
        "                event_start=event.get(\"start\"),\n"
        "                event_end=event.get(\"end\"),\n"
        "                sort_start_utc=event.get(\"sort_start_utc\"),\n"
        "                sort_end_utc=event.get(\"sort_end_utc\"),\n"
        "                location=event.get(\"location\"),\n"
        "                details=event.get(\"details\"),\n",
        "                event_start=event.get(\"start\"),\n"
        "                event_end=event.get(\"end\"),\n"
        "                sort_start_utc=event.get(\"sort_start_utc\"),\n"
        "                sort_end_utc=event.get(\"sort_end_utc\"),\n"
        "                display_when=event.get(\"display_when\"),\n"
        "                all_day=event.get(\"all_day\"),\n"
        "                location=event.get(\"location\"),\n"
        "                location_structured=event.get(\"location_structured\"),\n"
        "                details=event.get(\"details\"),\n",
        "calendar display/all-day/location fields",
    )

    build = replace_once(
        build,
        "                registration_url=event.get(\"registration_url\"),\n"
        "                info_url=event.get(\"info_url\"),\n"
        "                image_url=event.get(\"image_url\"),\n",
        "                registration_url=event.get(\"registration_url\"),\n"
        "                registration_available=bool(event.get(\"registration_available\", bool(event.get(\"registration_url\")))),\n"
        "                registration_open=event.get(\"registration_open\"),\n"
        "                registration_closed=event.get(\"registration_closed\"),\n"
        "                registration_at_maximum_capacity=event.get(\"registration_at_maximum_capacity\"),\n"
        "                registration_open_at=event.get(\"registration_open_at\"),\n"
        "                registration_close_at=event.get(\"registration_close_at\"),\n"
        "                registration_maximum_capacity=event.get(\"registration_maximum_capacity\"),\n"
        "                registration_categories=event.get(\"registration_categories\"),\n"
        "                registration_options=event.get(\"registration_options\"),\n"
        "                event_source=event.get(\"event_source\"),\n"
        "                event_sources=event.get(\"event_sources\"),\n"
        "                publicly_listed=event.get(\"publicly_listed\"),\n"
        "                info_url=event.get(\"info_url\"),\n"
        "                image_url=event.get(\"image_url\"),\n",
        "registration/runtime source fields",
    )

    registrations = replace_once(
        registrations,
        "        \"registration_url\": registration_url,\n"
        "        \"registration_open\": registration_open,\n",
        "        \"registration_url\": registration_url,\n"
        "        # This flag means an exact public registration action exists. Open/closed/full\n"
        "        # state remains separate so the runtime can describe those states precisely.\n"
        "        \"registration_available\": True,\n"
        "        \"registration_open\": registration_open,\n",
        "registration availability source flag",
    )

    registrations = replace_once(
        registrations,
        "        \"registration_url\",\n"
        "        \"registration_open\",\n",
        "        \"registration_url\",\n"
        "        \"registration_available\",\n"
        "        \"registration_open\",\n",
        "merge registration availability flag",
    )

    BUILD_PATH.write_text(build, encoding="utf-8")
    REG_PATH.write_text(registrations, encoding="utf-8")
    print("Applied guarded runtime event field fixes.")


if __name__ == "__main__":
    main()
