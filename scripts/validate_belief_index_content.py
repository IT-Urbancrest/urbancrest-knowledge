#!/usr/bin/env python3
"""Validate that belief article bodies are preserved completely in search-index.json."""

from pathlib import Path
import json
import yaml

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "runtime" / "search-index.json"
BELIEFS = ROOT / "knowledge" / "beliefs"

if not INDEX.exists():
    raise SystemExit(f"Missing {INDEX}. Run python scripts/build_search_index.py first.")

data = json.loads(INDEX.read_text(encoding="utf-8"))
records = {
    str(record.get("id")): record
    for record in data.get("records", [])
    if record.get("record_type") == "knowledge"
}

failures = []
belief_paths = sorted(BELIEFS.glob("*.md"))

for path in belief_paths:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        metadata = yaml.safe_load(parts[1]) or {}
        body = parts[2].strip() if len(parts) >= 3 else text.strip()
    else:
        metadata = {}
        body = text.strip()

    record_id = str(metadata.get("id") or path.relative_to(ROOT).as_posix())
    record = records.get(record_id)
    if not record:
        failures.append(f"{record_id}: missing from index")
        continue

    indexed = str(record.get("content") or "").strip()
    if indexed != body:
        failures.append(
            f"{record_id}: indexed content differs from source "
            f"(source={len(body)} chars, index={len(indexed)} chars)"
        )

if failures:
    print("Belief index validation FAILED:")
    for failure in failures:
        print(f" - {failure}")
    raise SystemExit(1)

print("Belief index validation passed.")
print(f"Verified {len(belief_paths)} belief articles with full source content.")
