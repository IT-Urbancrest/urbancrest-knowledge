#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "runtime" / "search-index.json"
TESTS_DIR = ROOT / "tests"


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def as_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def validate_index(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = index.get("records")
    if not isinstance(records, list):
        fail("runtime/search-index.json must contain a records array")

    if index.get("record_count") != len(records):
        fail(
            f"record_count says {index.get('record_count')} but records contains {len(records)} entries"
        )

    by_id: dict[str, dict[str, Any]] = {}
    for position, record in enumerate(records):
        if not isinstance(record, dict):
            fail(f"record {position} is not an object")
        record_id = str(record.get("id") or "").strip()
        if not record_id:
            fail(f"record {position} has no id")
        if record_id in by_id:
            first = by_id[record_id].get("path", "unknown")
            second = record.get("path", "unknown")
            fail(f"duplicate record id {record_id}: {first} <-> {second}")
        by_id[record_id] = record

    weekly = by_id.get("schedule.weekly")
    if not weekly:
        fail("schedule.weekly is missing")

    sunday_times = weekly.get("sunday_service_times") or []
    if not sunday_times:
        fail("schedule.weekly has no sunday_service_times")

    summary = str(weekly.get("summary") or "")
    missing_times = [str(value) for value in sunday_times if str(value) not in summary]
    if missing_times:
        fail(
            "schedule.weekly summary is out of sync with sunday_service_times: "
            + ", ".join(missing_times)
        )

    for record in records:
        if record.get("record_type") != "action_link":
            continue
        url = str(record.get("url") or "").strip()
        if url and not url.startswith("https://"):
            fail(f"action link {record['id']} must use HTTPS: {url}")

    return by_id


def validate_fixture_case(
    fixture_path: Path,
    case_number: int,
    case: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
) -> None:
    label = f"{fixture_path.name} case {case_number}"
    query = str(case.get("query") or "").strip()
    if not query:
        fail(f"{label} has no query")

    expected_record_id = str(case.get("expected_record") or "").strip()
    expected_record = None
    if expected_record_id:
        expected_record = by_id.get(expected_record_id)
        if expected_record is None:
            fail(f"{label} expects missing record {expected_record_id!r}")

    expected_member_count = case.get("expected_member_count")
    if expected_member_count is not None:
        if expected_record is None:
            fail(f"{label} has expected_member_count without expected_record")
        sermons = expected_record.get("sermons") or []
        if len(sermons) != int(expected_member_count):
            fail(
                f"{label} expects {expected_member_count} series members but "
                f"{expected_record_id} currently contains {len(sermons)}"
            )

    expected_title = str(case.get("expected_title") or "").strip()
    if expected_title and expected_record is not None:
        actual_title = str(expected_record.get("title") or "").strip()
        if actual_title != expected_title:
            fail(
                f"{label} expects title {expected_title!r} but {expected_record_id} is {actual_title!r}"
            )

    expected_url = str(case.get("expected_url") or "").strip()
    if expected_url and expected_record is not None:
        searchable = "\n".join(
            [
                as_text(expected_record.get("notes_url")),
                as_text(expected_record.get("url")),
                as_text(expected_record.get("resources")),
                as_text(expected_record.get("content")),
            ]
        )
        if expected_url not in searchable:
            fail(f"{label} expects URL not present in {expected_record_id}: {expected_url}")


def validate_fixtures(by_id: dict[str, dict[str, Any]]) -> int:
    fixture_count = 0
    case_count = 0

    for fixture_path in sorted(TESTS_DIR.glob("*.yaml")):
        fixture_count += 1
        data = yaml.safe_load(fixture_path.read_text(encoding="utf-8")) or {}
        cases = data.get("cases")
        if not isinstance(cases, list):
            fail(f"{fixture_path.name} must contain a cases list")

        for case_number, case in enumerate(cases, start=1):
            if not isinstance(case, dict):
                fail(f"{fixture_path.name} case {case_number} is not an object")
            case_count += 1
            validate_fixture_case(fixture_path, case_number, case, by_id)

    if fixture_count == 0:
        fail("no regression fixture YAML files were found in tests/")

    return case_count


def main() -> None:
    if not INDEX_PATH.exists():
        fail("runtime/search-index.json does not exist; run build_search_index.py first")

    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    if not isinstance(index, dict):
        fail("runtime/search-index.json root must be an object")

    by_id = validate_index(index)
    case_count = validate_fixtures(by_id)
    print(
        f"Validated {len(by_id)} search-index records and {case_count} regression fixture cases."
    )


if __name__ == "__main__":
    main()
