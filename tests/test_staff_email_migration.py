import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from staff_email_migration import migrate_staff_emails
from sync_events import clean_text as calendar_text
from sync_registrations import clean_text as registration_text


class StaffEmailMigrationTests(unittest.TestCase):
    def test_staff_addresses_and_mailto_links(self):
        self.assertEqual(
            migrate_staff_emails("Contact DSCHICK@URBANCREST.ORG or [Tanya](mailto:tbyrd@urbancrest.org)."),
            "Contact dschick@urbancrest.church or [Tanya](mailto:tbyrd@urbancrest.church).",
        )

    def test_shared_inboxes_and_similar_addresses_remain_unchanged(self):
        text = "office@urbancrest.org it@urbancrest.org other@urbancrest.org xlnichols@urbancrest.org lnichols@urbancrest.org.example lnichols@urbancrest.org.uk https://urbancrest.org lnichols@urbancrest.church"
        self.assertEqual(migrate_staff_emails(text), text)

    def test_calendar_and_registration_imports(self):
        for clean in (calendar_text, registration_text):
            self.assertEqual(clean("<p>Questions? JPROWS@urbancrest.org</p>"), "Questions? jprows@urbancrest.church")
            self.assertEqual(clean("Contact\nlnichols@urbancrest.org"), "Contact\nlnichols@urbancrest.church")

    def test_sentence_punctuation(self):
        self.assertEqual(migrate_staff_emails("Email jprows@urbancrest.org."), "Email jprows@urbancrest.church.")

    def test_migration_is_idempotent(self):
        text = migrate_staff_emails("dbickers@urbancrest.org")
        self.assertEqual(migrate_staff_emails(text), text)


if __name__ == "__main__":
    unittest.main()
