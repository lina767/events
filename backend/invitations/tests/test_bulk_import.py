from django.test import TestCase
from events.tests.factories import make_event
from people.models import DuplicateCandidate, Person, PersonEmail

from invitations.models import InvitationEventType
from invitations.services.bulk_import import bulk_invite_from_rows


class BulkInviteFromRowsTests(TestCase):
    def test_creates_a_person_and_invitation_per_new_row(self):
        event = make_event()
        rows = [
            {"name": "Amira Hassan", "email": "amira@example.com"},
            {"name": "Jonas Weber", "email": "jonas@example.com"},
        ]

        created = bulk_invite_from_rows(event, rows)

        self.assertEqual(len(created), 2)
        self.assertEqual(Person.objects.count(), 2)
        self.assertTrue(all(e.event_type == InvitationEventType.INVITED for e in created))

    def test_reuses_existing_person_by_exact_email(self):
        event = make_event()
        existing = Person.objects.create(display_name="Amira Hassan")
        PersonEmail.objects.create(person=existing, email="amira@example.com", is_primary=True)

        created = bulk_invite_from_rows(event, [{"name": "Amira Hassan", "email": "amira@example.com"}])

        self.assertEqual(Person.objects.count(), 1)
        self.assertEqual(created[0].person_id, existing.person_id)

    def test_new_row_with_different_email_still_flags_as_duplicate_candidate(self):
        """
        The old system only deduped on exact email match. This is the
        behavior it's replacing: a name-variant with a different email is
        a brand-new Person, but Module 1's matching still catches it.
        """
        event = make_event()
        Person.objects.create(display_name="Amira Hassan")

        bulk_invite_from_rows(event, [{"name": "Amira Hassan", "email": "a.hassan@example.com"}])

        self.assertEqual(Person.objects.count(), 2)
        self.assertEqual(DuplicateCandidate.objects.count(), 1)

    def test_duplicate_row_in_the_same_spreadsheet_only_invited_once(self):
        event = make_event()
        rows = [
            {"name": "Amira Hassan", "email": "amira@example.com"},
            {"name": "Amira Hassan", "email": "amira@example.com"},
        ]

        created = bulk_invite_from_rows(event, rows)

        self.assertEqual(len(created), 1)
