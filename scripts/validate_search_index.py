#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime
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


def case_prompt(case: dict[str, Any]) -> str:
    """Return the user prompt from any fixture convention in this repository."""
    return str(case.get("query") or case.get("question") or "").strip()


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

    freshness = index.get("freshness")
    if not isinstance(freshness, dict):
        fail("runtime/search-index.json must contain freshness metadata")

    for key in ("calendar", "small_groups"):
        item = freshness.get(key)
        if not isinstance(item, dict):
            fail(f"freshness.{key} is missing")

        generated_at = str(item.get("generated_at") or "").strip()
        if not generated_at:
            fail(f"freshness.{key}.generated_at is missing")
        try:
            parsed = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        except ValueError:
            fail(f"freshness.{key}.generated_at is not ISO-8601: {generated_at}")
        if parsed.tzinfo is None:
            fail(f"freshness.{key}.generated_at must include a timezone")

        try:
            max_age_hours = float(item.get("max_age_hours"))
        except (TypeError, ValueError):
            fail(f"freshness.{key}.max_age_hours must be numeric")
        if max_age_hours <= 0:
            fail(f"freshness.{key}.max_age_hours must be positive")

        source_path_value = str(item.get("source_path") or "").strip()
        heartbeat_field = str(item.get("heartbeat_field") or "generated_at").strip()
        if not source_path_value:
            fail(f"freshness.{key}.source_path is missing")
        source_path = ROOT / source_path_value
        if not source_path.is_file():
            fail(f"freshness.{key} source does not exist: {source_path_value}")
        source_data = yaml.safe_load(source_path.read_text(encoding="utf-8")) or {}
        expected_heartbeat = str(source_data.get(heartbeat_field) or "").strip()
        if generated_at != expected_heartbeat:
            fail(
                f"freshness.{key}.generated_at does not match {source_path_value} "
                f"field {heartbeat_field}"
            )

        fallback_action_key = str(item.get("fallback_action_key") or "").strip()
        if not fallback_action_key:
            fail(f"freshness.{key}.fallback_action_key is missing")
        fallback = by_id.get(f"action_link.{fallback_action_key}")
        if not fallback:
            fail(
                f"freshness.{key} references missing fallback action "
                f"action_link.{fallback_action_key}"
            )
        if not str(fallback.get("url") or "").startswith("https://"):
            fail(f"freshness.{key} fallback action must use HTTPS")

    return by_id


def fixture_cases(fixture_path: Path, data: dict[str, Any]) -> tuple[str, list[Any]]:
    """Return regression cases from either supported fixture convention.

    The repository contains established fixtures using either top-level ``cases:``
    or top-level ``tests:``. Individual test prompts may be named ``query`` or
    ``question``. Validation supports these historical formats rather than forcing
    a bulk fixture rewrite.
    """
    cases = data.get("cases")
    if isinstance(cases, list):
        return "cases", cases

    tests = data.get("tests")
    if isinstance(tests, list):
        return "tests", tests

    fail(f"{fixture_path.name} must contain either a cases list or a tests list")
    raise AssertionError("unreachable")


def require_record_exists(
    fixture_path: Path,
    case_number: int,
    field_name: str,
    record_id: Any,
    by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    value = str(record_id or "").strip()
    if not value:
        return None
    record = by_id.get(value)
    if record is None:
        fail(
            f"{fixture_path.name} case {case_number} field {field_name} "
            f"references missing record {value!r}"
        )
    return record


def validate_record_id_list(
    fixture_path: Path,
    case_number: int,
    label: str,
    value: Any,
    by_id: dict[str, dict[str, Any]],
) -> None:
    if value in (None, []):
        return
    if not isinstance(value, list):
        fail(f"{fixture_path.name} case {case_number} field {label} must be a list")
    for record_id in value:
        require_record_exists(fixture_path, case_number, label, record_id, by_id)


def validate_current_case(
    fixture_path: Path,
    case_number: int,
    case: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
) -> None:
    """Validate the newer ``cases:`` fixture format."""
    label = f"{fixture_path.name} case {case_number}"
    prompt = case_prompt(case)
    if not prompt:
        fail(f"{label} has no query or question")

    expected_record_id = str(case.get("expected_record") or "").strip()
    expected_record = None
    if expected_record_id:
        expected_record = require_record_exists(
            fixture_path,
            case_number,
            "expected_record",
            expected_record_id,
            by_id,
        )

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


def validate_legacy_test(
    fixture_path: Path,
    case_number: int,
    case: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
) -> None:
    """Validate declarations in the older ``tests:`` fixture formats.

    These files describe runtime retrieval expectations that this lightweight index
    validator cannot execute. We can still catch stale/broken fixture references by
    verifying every explicitly named record and action-link key exists.
    """
    label = f"{fixture_path.name} test {case_number}"
    prompt = case_prompt(case)
    if not prompt:
        fail(f"{label} has no query or question")

    expected = case.get("expected") or {}
    if not isinstance(expected, dict):
        fail(f"{label} expected must be an object")

    # Single explicit record references.
    for field_name in (
        "first_record_id",
        "required_record_id",
        "must_not_first_record_id",
    ):
        value = expected.get(field_name)
        if value:
            require_record_exists(
                fixture_path,
                case_number,
                f"expected.{field_name}",
                value,
                by_id,
            )

    # List-based record references used by different generations of fixtures.
    for field_name in (
        "required_record_ids",
        "retrieved_record_ids_include",
        "retrieved_record_ids_exclude",
    ):
        validate_record_id_list(
            fixture_path,
            case_number,
            f"expected.{field_name}",
            expected.get(field_name),
            by_id,
        )

    # Action keys correspond to action_link.<key> records in the compiled index.
    required_action_keys = expected.get("required_action_keys") or []
    if required_action_keys and not isinstance(required_action_keys, list):
        fail(f"{label} expected.required_action_keys must be a list")
    for action_key in required_action_keys:
        action_id = f"action_link.{str(action_key).strip()}"
        require_record_exists(
            fixture_path,
            case_number,
            "expected.required_action_keys",
            action_id,
            by_id,
        )


def validate_fixtures(by_id: dict[str, dict[str, Any]]) -> tuple[int, int, int]:
    fixture_count = 0
    case_count = 0
    current_case_count = 0
    legacy_test_count = 0

    for fixture_path in sorted(TESTS_DIR.glob("*.yaml")):
        fixture_count += 1
        data = yaml.safe_load(fixture_path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            fail(f"{fixture_path.name} root must be an object")

        convention, cases = fixture_cases(fixture_path, data)

        for case_number, case in enumerate(cases, start=1):
            if not isinstance(case, dict):
                fail(f"{fixture_path.name} item {case_number} is not an object")
            case_count += 1
            if convention == "cases":
                current_case_count += 1
                validate_current_case(fixture_path, case_number, case, by_id)
            else:
                legacy_test_count += 1
                validate_legacy_test(fixture_path, case_number, case, by_id)

    if fixture_count == 0:
        fail("no regression fixture YAML files were found in tests/")

    return case_count, current_case_count, legacy_test_count


def main() -> None:
    if not INDEX_PATH.exists():
        fail("runtime/search-index.json does not exist; run build_search_index.py first")

    index = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    if not isinstance(index, dict):
        fail("runtime/search-index.json root must be an object")

    by_id = validate_index(index)
    case_count, current_case_count, legacy_test_count = validate_fixtures(by_id)
    print(
        f"Validated {len(by_id)} search-index records and {case_count} regression declarations "
        f"({current_case_count} current-format cases, {legacy_test_count} legacy-format tests)."
    )


if __name__ == "__main__":
    main()
