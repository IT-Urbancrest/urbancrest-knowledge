#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = ROOT / "runtime" / "search-index.json"
MAX_SUPPLEMENTAL_TERMS = 14
MAX_TERM_LENGTH = 220
CONTENT_CAP = 2400


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = re.sub(r"\s+", " ", str(value or "")).strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def markdown_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return text.strip()
    parts = text.split("---\n", 2)
    return parts[2].strip() if len(parts) >= 3 else text.strip()


def clean_markdown_phrase(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[*_>#]+", " ", text)
    text = re.sub(r"^\s*[-+]\s+", "", text)
    text = re.sub(r"^\s*\d+[.)]\s+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def supplemental_terms(body: str) -> list[str]:
    if len(body) <= CONTENT_CAP:
        return []

    candidates: list[str] = []

    # Headings are compact, high-signal retrieval phrases.
    for match in re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*$", body):
        heading = clean_markdown_phrase(match.group(1))
        if 3 <= len(heading) <= MAX_TERM_LENGTH:
            candidates.append(heading)

    # The builder keeps the first CONTENT_CAP characters in prompt content. Start
    # supplemental extraction only after the next sentence/paragraph boundary so
    # a hard character cap can never produce a partial leading word or sentence.
    tail_offset = CONTENT_CAP
    boundary = re.search(r"(?:[.!?](?:\s+|$)|\n{2,})", body[CONTENT_CAP:])
    if boundary:
        tail_offset += boundary.end()
    tail = body[tail_offset:]

    raw_chunks = re.split(r"(?<=[.!?])\s+|\n{2,}", tail)
    for chunk in raw_chunks:
        phrase = clean_markdown_phrase(chunk)
        if not phrase or len(phrase) < 20 or len(phrase) > MAX_TERM_LENGTH:
            continue
        words = re.findall(r"[A-Za-z0-9']+", phrase)
        if len(words) < 4:
            continue
        candidates.append(phrase)
        if len(unique(candidates)) >= MAX_SUPPLEMENTAL_TERMS:
            break

    return unique(candidates)[:MAX_SUPPLEMENTAL_TERMS]


def enrich_long_markdown_records(payload: dict[str, Any]) -> int:
    enriched = 0
    for record in payload.get("records", []):
        if not isinstance(record, dict):
            continue
        relative = str(record.get("path") or "")
        if not relative.startswith("knowledge/") or not relative.endswith(".md"):
            continue
        if Path(relative).name.casefold() == "readme.md":
            continue
        source_path = ROOT / relative
        if not source_path.is_file():
            continue

        body = markdown_body(source_path)
        extras = supplemental_terms(body)
        if not extras:
            continue

        existing = [str(value) for value in (record.get("search_terms") or [])]
        existing_keys = {value.casefold() for value in existing}
        merged = unique([*existing, *extras])
        if merged != existing:
            record["search_terms"] = merged
            record["supplemental_search_term_count"] = len(
                [value for value in merged if value.casefold() not in existing_keys]
            )
            enriched += 1
    return enriched


def previous_committed_index() -> dict[str, Any] | None:
    try:
        raw = subprocess.check_output(
            ["git", "show", "HEAD:runtime/search-index.json"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        )
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError):
        return None


def semantic_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(payload)
    normalized.pop("generated_at", None)
    return normalized


def main() -> None:
    if not INDEX_PATH.exists():
        raise SystemExit("runtime/search-index.json does not exist; build it first")

    payload = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("runtime/search-index.json root must be an object")

    enriched = enrich_long_markdown_records(payload)
    previous = previous_committed_index()

    preserved_timestamp = False
    if previous and semantic_payload(previous) == semantic_payload(payload):
        previous_generated_at = previous.get("generated_at")
        if previous_generated_at:
            payload["generated_at"] = previous_generated_at
            preserved_timestamp = True

    INDEX_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    timestamp_message = (
        "preserved generated_at because the semantic index is unchanged"
        if preserved_timestamp
        else "kept the new generated_at because index content changed"
    )
    print(
        f"Finalized search index: enriched {enriched} long Markdown records; "
        f"{timestamp_message}."
    )


if __name__ == "__main__":
    main()
