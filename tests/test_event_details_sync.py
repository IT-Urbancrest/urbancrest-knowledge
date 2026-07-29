import importlib.util
import sys
import types
import unittest
from pathlib import Path


# The extraction helpers do not need network or recurrence parsing. Stub these
# optional imports so the test can run without installing the workflow's full
# dependency set in a local development environment.
sys.modules.setdefault("recurring_ical_events", types.ModuleType("recurring_ical_events"))
icalendar_stub = types.ModuleType("icalendar")
icalendar_stub.Calendar = object
sys.modules.setdefault("icalendar", icalendar_stub)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_events.py"
SPEC = importlib.util.spec_from_file_location("sync_events", SCRIPT)
sync_events = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(sync_events)


class FakeComponent(dict):
    pass


class EventDetailsExtractionTests(unittest.TestCase):
    def test_rich_details_are_kept_without_duplicate_description(self):
        component = FakeComponent({
            "DESCRIPTION": "Join us for Wednesday Night Dinner.",
            "X-ALT-DESC": (
                "<p>Join us for Wednesday Night Dinner.</p>"
                "<p><strong>Menu:</strong></p>"
                "<ul><li>Chicken</li><li>Mashed potatoes</li></ul>"
            ),
        })
        description = sync_events.clean_text(component.get("DESCRIPTION"))
        details = sync_events.extract_details(component, description)
        self.assertIn("Menu:", details)
        self.assertIn("Chicken", details)
        self.assertNotEqual(
            sync_events.normalized_content(details),
            sync_events.normalized_content(description),
        )

    def test_duplicate_alt_description_is_ignored(self):
        component = FakeComponent({
            "DESCRIPTION": "Join us for dinner.",
            "X-ALT-DESC": "<p>Join us for dinner.</p>",
        })
        description = sync_events.clean_text(component.get("DESCRIPTION"))
        self.assertEqual(sync_events.extract_details(component, description), "")

    def test_custom_details_property_is_supported(self):
        component = FakeComponent({
            "DESCRIPTION": "Join us for dinner.",
            "X-PLANNING-CENTER-DETAILS": "Menu: Tacos and rice",
        })
        description = sync_events.clean_text(component.get("DESCRIPTION"))
        self.assertIn(
            "Tacos and rice",
            sync_events.extract_details(component, description),
        )


if __name__ == "__main__":
    unittest.main()
