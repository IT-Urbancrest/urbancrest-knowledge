#!/usr/bin/env python3
from pathlib import Path

BUILDER = Path("scripts/build_search_index.py")
VALIDATOR = Path("scripts/validate_search_index.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one old marker, found {count}")
    return text.replace(old, new, 1)


def patch_builder(text: str) -> str:
    marker = "\n\ndef main() -> None:\n"
    helper = r'''


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
'''
    if "def live_freshness_metadata()" not in text:
        if marker not in text:
            raise RuntimeError("builder main marker not found")
        text = text.replace(marker, helper + marker, 1)

    old_payload = '''        "source_rules": yaml.safe_load((ROOT / "registry/runtime-sources.yaml").read_text(encoding="utf-8")),
        "records": records,
'''
    new_payload = '''        "source_rules": yaml.safe_load((ROOT / "registry/runtime-sources.yaml").read_text(encoding="utf-8")),
        "freshness": live_freshness_metadata(),
        "records": records,
'''
    return replace_once(text, old_payload, new_payload, "builder freshness payload")


def patch_validator(text: str) -> str:
    if "from datetime import datetime" not in text:
        text = replace_once(
            text,
            "import json\nfrom pathlib import Path\n",
            "import json\nfrom datetime import datetime\nfrom pathlib import Path\n",
            "validator datetime import",
        )

    old_block = '''    for record in records:
        if record.get("record_type") != "action_link":
            continue
        url = str(record.get("url") or "").strip()
        if url and not url.startswith("https://"):
            fail(f"action link {record['id']} must use HTTPS: {url}")

    return by_id
'''
    new_block = '''    for record in records:
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
'''
    return replace_once(text, old_block, new_block, "validator freshness checks")


def main() -> None:
    builder = BUILDER.read_text(encoding="utf-8")
    validator = VALIDATOR.read_text(encoding="utf-8")
    BUILDER.write_text(patch_builder(builder), encoding="utf-8")
    VALIDATOR.write_text(patch_validator(validator), encoding="utf-8")
    print("Applied live freshness contract compiler and validation.")


if __name__ == "__main__":
    main()
