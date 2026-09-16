import importlib.util
from pathlib import Path
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_search_index", ROOT / "scripts/build_search_index.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class EventSearchResponseTests(unittest.TestCase):
    def setUp(self):
        self.rules = yaml.safe_load((ROOT / "registry/event-overrides.yaml").read_text())["search_response_rules"]
        self.event = {
            "title": "Men's Summit",
            "summary": "Men's Summit 2027: Where God Sharpens Man",
            "description": "WHERE GOD SHARPENS MAN",
            "details": "Register: https://urbancrest.churchcenter.com/registrations/events/3894841",
            "registration_url": "https://urbancrest.churchcenter.com/registrations/events/3894841",
            "registration_available": True,
            "registration_open": False,
            "info_url": "https://urbancrest.church/events/mens-summit",
            "image_url": "https://example.com/artwork.jpg",
        }

    def test_mens_summit_has_one_website_destination_and_no_tagline(self):
        result = module.event_search_response(self.event, self.rules)
        self.assertEqual(result["registration_url"], "https://urbancrest.church/events/mens-summit")
        self.assertIsNone(result["info_url"])
        for field in ("summary", "description", "details"):
            self.assertNotIn("where god sharpens man", result[field].casefold())
            self.assertNotIn("churchcenter.com", result[field])
        self.assertEqual(result["image_url"], self.event["image_url"])
        self.assertFalse(result["registration_open"])
        self.assertIn("churchcenter.com", self.event["registration_url"])

    def test_other_events_are_unchanged(self):
        other = dict(self.event, title="Trail of Treats")
        self.assertEqual(module.event_search_response(other, self.rules), other)


if __name__ == "__main__":
    unittest.main()
