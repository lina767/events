from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from people.models import DuplicateCandidate, Person
from people.tests.factories import make_person


class ScanDuplicatesCommandTests(TestCase):
    def test_scan_finds_duplicates_created_outside_the_signal(self):
        # bulk_create bypasses post_save, simulating a legacy data import
        # that never went through the normal creation path.
        Person.objects.bulk_create(
            [Person(display_name="Jane Doe"), Person(display_name="Jane Doe")]
        )
        self.assertEqual(DuplicateCandidate.objects.count(), 0)

        call_command("scan_duplicates", stdout=StringIO())

        self.assertEqual(DuplicateCandidate.objects.count(), 1)


class FlagStalePersonsCommandTests(TestCase):
    def test_flags_persons_never_verified(self):
        make_person(display_name="Jane Doe")

        call_command("flag_stale_persons", stdout=StringIO())

        self.assertTrue(Person.objects.get(display_name="Jane Doe").flagged_for_review)

    def test_does_not_flag_recently_verified_persons(self):
        make_person(display_name="Jane Doe", last_verified_at=timezone.now())

        call_command("flag_stale_persons", stdout=StringIO())

        self.assertFalse(Person.objects.get(display_name="Jane Doe").flagged_for_review)
