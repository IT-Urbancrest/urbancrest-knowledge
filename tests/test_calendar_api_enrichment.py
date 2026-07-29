import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path

sys.modules.setdefault("recurring_ical_events", types.ModuleType("recurring_ical_events"))
icalendar_stub = types.ModuleType("icalendar")
icalendar_stub.Calendar = object
sys.modules.setdefault("icalendar", icalendar_stub)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync_events.py"
SPEC = importlib.util.spec_from_file_location("sync_events_api", SCRIPT)
sync_events = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(sync_events)


class CalendarApiEnrichmentTests(unittest.TestCase):
    def test_planning_center_uid_is_parsed(self):
        parsed = sync_events.parse_planning_center_uid(
            "ET-29468516-216277428@resources.planningcenteronline.com"
        )
        self.assertEqual(parsed["event_time_id"], "29468516")
        self.assertEqual(parsed["event_instance_id"], "216277428")

    def test_json_api_records_are_mapped_to_instance(self):
        instances = [
            {
                "type": "EventInstance",
                "id": "216277428",
                "attributes": {
                    "description": "<p><strong>Menu:</strong> Tacos and rice</p>",
                    "church_center_url": "https://urbancrest.churchcenter.com/calendar/event/1",
                    "location": "Gymnasium",
                },
                "relationships": {
                    "event": {"data": {"type": "Event", "id": "9001"}}
                },
            }
        ]
        included = [
            {
                "type": "Event",
                "id": "9001",
                "attributes": {
                    "summary": "Join us for Wednesday Night Dinner.",
                    "description": "<p><strong>Menu:</strong> Tacos and rice</p>",
                    "registration_url": None,
                    "visible_in_church_center": True,
                },
            }
        ]
        mapped = sync_events.build_calendar_api_enrichment(
            instances, included, {"216277428"}
        )
        event = mapped["216277428"]
        self.assertEqual(event["planning_center_event_id"], "9001")
        self.assertIn("Tacos and rice", event["event_description"])
        self.assertIn("Tacos and rice", event["instance_description"])

    def test_api_rich_description_becomes_nonduplicate_details(self):
        api_data = {
            "event_summary": "Join us for Wednesday Night Dinner.",
            "instance_description": "",
            "event_description": (
                "Join us for Wednesday Night Dinner.\n\n"
                "Menu: Chicken, mashed potatoes, and green beans"
            ),
        }
        details = sync_events.extract_api_details(
            api_data, "Join us for Wednesday Night Dinner."
        )
        self.assertEqual(
            details,
            "Menu: Chicken, mashed potatoes, and green beans",
        )

    def test_plain_summary_is_not_duplicated_as_details(self):
        api_data = {
            "event_summary": "Join us for dinner.",
            "instance_description": "Join us for dinner.",
            "event_description": "Join us for dinner.",
        }
        self.assertEqual(
            sync_events.extract_api_details(api_data, "Join us for dinner."),
            "",
        )


if __name__ == "__main__":
    unittest.main()
