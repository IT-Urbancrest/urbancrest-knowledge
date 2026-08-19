#!/usr/bin/env python3
"""
Apply the Urbancrest 0.10.27 search-index patch.

`record_base()` currently truncates every record's content to 2400 characters.
Deterministic doctrine answer shaping needs the full canonical belief article so
it can retrieve H2 sections that occur later in the file.

This patch keeps the 2400-character limit for ordinary records, but preserves
full content for Markdown files under knowledge/beliefs/.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "scripts" / "build_search_index.py"

if not TARGET.exists():
    raise SystemExit(f"Could not find {TARGET}")

text = TARGET.read_text(encoding="utf-8")
original = text

old = """def truncate(value: str, limit: int = 2400) -> str:
    value = value.strip()
    return value if len(value) <= limit else value[: limit - 3].rstrip() + "..."
"""
new = """def truncate(value: str, limit: int | None = 2400) -> str:
    value = value.strip()
    if limit is None:
        return value
    return value if len(value) <= limit else value[: limit - 3].rstrip() + "..."
"""
if old in text:
    text = text.replace(old, new, 1)
elif "def truncate(value: str, limit: int | None = 2400)" not in text:
    raise SystemExit("Patch stopped: could not find the expected truncate() function.")

old = """    resources: list[str] | None = None,
    **extra: Any,
"""
new = """    resources: list[str] | None = None,
    content_limit: int | None = 2400,
    **extra: Any,
"""
if old in text:
    text = text.replace(old, new, 1)
elif "content_limit: int | None = 2400" not in text:
    raise SystemExit("Patch stopped: could not find the expected record_base() signature.")

old = """        "content": truncate(content),
"""
new = """        "content": truncate(content, content_limit),
"""
if old in text:
    text = text.replace(old, new, 1)
elif '"content": truncate(content, content_limit),' not in text:
    raise SystemExit("Patch stopped: could not find the expected record content line.")

old = """                summary=str(metadata.get("summary") or ""),
                content=body,
                priority=int(metadata.get("priority") or 50),
"""
new = """                summary=str(metadata.get("summary") or ""),
                content=body,
                content_limit=None if relative.startswith("knowledge/beliefs/") else 2400,
                priority=int(metadata.get("priority") or 50),
"""
if old in text:
    text = text.replace(old, new, 1)
elif 'content_limit=None if relative.startswith("knowledge/beliefs/") else 2400,' not in text:
    raise SystemExit("Patch stopped: could not find the Markdown record construction block.")

if text == original:
    print("0.10.27 index patch is already applied.")
    sys.exit(0)

TARGET.write_text(text, encoding="utf-8")
print(f"Patched {TARGET}")
print("Belief Markdown will now be indexed with full content.")
print("Other record types retain the existing 2400-character default.")
