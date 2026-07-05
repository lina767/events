from django.test import TestCase
from events.tests.factories import make_event
from people.tests.factories import make_person

from nominations.models import NominationStatus
from nominations.services.bundling import find_group, group_pending
from nominations.tests.factories import make_nomination


class GroupPendingTests(TestCase):
    def test_two_nominators_proposing_the_same_new_contact_are_bundled(self):
        event = make_event()
        make_nomination(event=event, nominee_name="Amira Hassan")
        make_nomination(event=event, nominee_name="Amira Hassan")
        make_nomination(event=event, nominee_name="Someone Else")

        groups = group_pending(event)

        sizes = sorted(len(g) for g in groups)
        self.assertEqual(sizes, [1, 2])

    def test_bundling_by_existing_nominee_person(self):
        event = make_event()
        nominee = make_person(display_name="Amira Hassan")
        make_nomination(event=event, nominee=nominee)
        make_nomination(event=event, nominee=nominee)

        groups = group_pending(event)

        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 2)

    def test_decided_nominations_are_excluded_from_grouping(self):
        event = make_event()
        n1 = make_nomination(event=event, nominee_name="Amira Hassan")
        make_nomination(event=event, nominee_name="Amira Hassan")
        n1.status = NominationStatus.APPROVED
        n1.save(update_fields=["status"])

        groups = group_pending(event)

        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 1)

    def test_find_group_includes_the_nomination_itself(self):
        event = make_event()
        solo = make_nomination(event=event, nominee_name="Solo Nominee")

        group = find_group(solo)

        self.assertEqual(group, [solo])
