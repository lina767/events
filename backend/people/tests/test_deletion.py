from django.test import TestCase

from people.models import ConsentStatus, PersonDeletionLog
from people.services.deletion import DeletionError, erase_person
from people.tests.factories import make_email, make_person


class ErasePersonTests(TestCase):
    def test_erase_scrubs_personal_data(self):
        person = make_person(display_name="Jane Doe", organization="Acme Corp", sector_tags=["tech"])
        make_email(person, "jane@example.com", is_primary=True)

        erase_person(person, performed_by="dpo@example.com")

        person.refresh_from_db()
        self.assertEqual(person.display_name, "Deleted person")
        self.assertEqual(person.organization, "")
        self.assertEqual(person.sector_tags, [])
        self.assertEqual(person.consent_status, ConsentStatus.REVOKED)
        self.assertTrue(person.is_deleted)
        self.assertFalse(person.is_active)
        self.assertEqual(person.emails.count(), 0)

    def test_erase_creates_an_audit_log_entry(self):
        person = make_person(display_name="Jane Doe")

        log = erase_person(
            person, performed_by="dpo@example.com", requested_by="jane@example.com", reason="GDPR request"
        )

        self.assertEqual(PersonDeletionLog.objects.count(), 1)
        self.assertEqual(log.person_id, person.person_id)
        self.assertEqual(log.requested_by, "jane@example.com")
        self.assertEqual(log.reason, "GDPR request")

    def test_cannot_erase_twice(self):
        person = make_person(display_name="Jane Doe")
        erase_person(person, performed_by="dpo@example.com")

        with self.assertRaises(DeletionError):
            erase_person(person, performed_by="dpo@example.com")

    def test_person_id_is_preserved_as_a_stable_tombstone(self):
        person = make_person(display_name="Jane Doe")
        original_id = person.person_id

        erase_person(person, performed_by="dpo@example.com")

        person.refresh_from_db()
        self.assertEqual(person.person_id, original_id)
