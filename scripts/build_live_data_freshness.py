#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "registry" / "runtime-sources.yaml"
OUTPUT_PATH = ROOT / "runtime" / "live-data-freshness.json"


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain a YAML mapping")
    return data


def positive_number(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if number <= 0:
        raise ValueError(f"{label} must be positive")
    return number


def clean_number(value: float) -> int | float:
    return int(value) if value.is_integer() else value


def main() -> None:
    policy = load_yaml(POLICY_PATH)
    freshness = policy.get("freshness")
    if not isinstance(freshness, dict) or not freshness:
        raise ValueError("registry/runtime-sources.yaml must define freshness policies")

    result: dict[str, Any] = {
        "schema_version": "1.0",
        "timezone": "America/New_York",
        "sources": {},
    }

    for key, raw_policy in freshness.items():
        if not isinstance(raw_policy, dict):
            raise ValueError(f"freshness.{key} must be a mapping")

        heartbeat_path = str(raw_policy.get("heartbeat_path") or "").strip()
        heartbeat_field = str(raw_policy.get("heartbeat_field") or "generated_at").strip()
        if not heartbeat_path:
            raise ValueError(f"freshness.{key}.heartbeat_path is required")

        heartbeat = load_yaml(ROOT / heartbeat_path)
        generated_at = str(heartbeat.get(heartbeat_field) or "").strip()
        if not generated_at:
            raise ValueError(
                f"freshness.{key} source {heartbeat_path} has no {heartbeat_field} value"
            )

        # `max_age_hours` remains the compatibility hard cutoff consumed by the
        # current Base44 runtime. The normal window controls when a freshness
        # caveat begins; the hard cutoff controls when current live details must
        # be refused.
        hard_value = raw_policy.get("grace_max_age_hours", raw_policy.get("max_age_hours"))
        if hard_value is None:
            hard_value = raw_policy.get("max_age_hours")
        normal_value = raw_policy.get("normal_max_age_hours", hard_value)

        normal_hours = positive_number(normal_value, f"freshness.{key}.normal_max_age_hours")
        hard_hours = positive_number(hard_value, f"freshness.{key}.max_age_hours")
        if normal_hours > hard_hours:
            raise ValueError(
                f"freshness.{key}.normal_max_age_hours cannot exceed the hard cutoff"
            )

        result["sources"][str(key)] = {
            "generated_at": generated_at,
            "normal_max_age_hours": clean_number(normal_hours),
            "max_age_hours": clean_number(hard_hours),
            "fallback_action_key": str(raw_policy.get("fallback_action_key") or "").strip(),
            "grace_behavior": str(raw_policy.get("grace_behavior") or "").strip(),
            "stale_behavior": str(raw_policy.get("stale_behavior") or "").strip(),
        }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
