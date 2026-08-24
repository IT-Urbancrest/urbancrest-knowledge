#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "sync_events.py"

spec = importlib.util.spec_from_file_location("urbancrest_sync_events", MODULE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit("ERROR: could not load scripts/sync_events.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

calendar_url = "https://urbancrest.churchcenter.com/calendar/event/216277432"
external_url = "https://urbancrest.church/events/pickleball"

assert module.public_calendar_info_url(
    None,
    {
        "church_center_url": calendar_url,
        "visible_in_church_center": False,
    },
) is None, "hidden Church Center calendar links must be suppressed"

assert module.public_calendar_info_url(
    None,
    {
        "church_center_url": calendar_url,
        "visible_in_church_center": True,
    },
) == calendar_url, "public Church Center calendar links should be retained"

assert module.public_calendar_info_url(
    calendar_url,
    {
        "visible_in_church_center": None,
    },
) is None, "Church Center calendar links require explicit public visibility"

assert module.public_calendar_info_url(
    external_url,
    {
        "visible_in_church_center": False,
    },
) == external_url, "non-Church-Center information links should not be suppressed"

print("Event link policy tests passed.")
