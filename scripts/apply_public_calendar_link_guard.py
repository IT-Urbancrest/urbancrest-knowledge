#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts" / "sync_events.py"

text = PATH.read_text(encoding="utf-8")

helper = '''\n\ndef public_calendar_info_url(\n    info_url: str | None,\n    api_data: dict[str, object],\n) -> str | None:\n    """Return only public-safe event information URLs.\n\n    Church Center calendar-instance URLs are only trustworthy when the parent\n    Planning Center event is explicitly visible in Church Center. Registration\n    URLs are handled separately and are not affected by this policy.\n    """\n    candidate = clean_text(info_url) or clean_text(api_data.get("church_center_url"))\n    if not candidate:\n        return None\n\n    if "churchcenter.com/calendar/event/" in candidate.casefold():\n        if api_data.get("visible_in_church_center") is not True:\n            return None\n\n    return candidate\n'''

if "def public_calendar_info_url(" not in text:
    marker = "\n\ndef extract_image(component, *text_fields: str) -> str | None:\n"
    if marker not in text:
        raise SystemExit("ERROR: extract_image marker not found")
    text = text.replace(marker, helper + marker, 1)

old_info = '        info_url = info_url or clean_text(api_data.get("church_center_url")) or None\n'
new_info = '        info_url = public_calendar_info_url(info_url, api_data)\n'
if old_info in text:
    text = text.replace(old_info, new_info, 1)
elif new_info not in text:
    raise SystemExit("ERROR: info_url assignment marker not found")

old_field = '            "info_url": info_url,\n            "image_url": image_url,\n'
new_field = '''            "info_url": info_url,\n            "publicly_listed": (\n                api_data.get("visible_in_church_center")\n                if isinstance(api_data.get("visible_in_church_center"), bool)\n                else None\n            ),\n            "image_url": image_url,\n'''
if old_field in text:
    text = text.replace(old_field, new_field, 1)
elif new_field not in text:
    raise SystemExit("ERROR: event info_url field marker not found")

PATH.write_text(text, encoding="utf-8")
print("Applied public Church Center calendar-link guard.")
