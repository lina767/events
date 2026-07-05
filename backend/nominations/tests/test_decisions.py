from django.dispatch import receiver
from django.test import TestCase
from events.tests.factories import make_event
from people.models import Person
from people.tests.factories import make_person

from nominations.models import NominationStatus
from nominations.services.decisions import approve, batch_decide, reject, waitlist
from nominations.signals import nomination_approved
from nominations.tests.factories import make_nomination


class ApproveTests(TestCase):
    def test_approving_a_new_contact_creates_a_person(self):
        nomination = make_nomination(nominee_name="Amira Hassan", nominee_organization="Acme")

        nominee, group = approve(nomination, decided_by="cfo@example.com")

        self.assertEqual(Person.objects.filter(display_name="Amira Hassan").count(), 1)
        self.assertEqual(nominee.organization, "Acme")
        self.assertEqual(group, [nomination])
        nomination.refresh_from_db()
        self.assertEqual(nomination.status, NominationStatus.APPROVED)
        self.assertEqual(nomination.nominee_id, nominee.person_id)

    def test_approving_one_of_a_bundle_approves_all_of_it(self):
        event = make_event()
        n1 = make_nomination(event=event, nominee_name="Amira Hassan")
        n2 = make_nomination(event=event, nominee_name="Amira Hassan")

        nominee, group = approve(n1, decided_by="cfo@example.com")

        self.assertEqual({n.pk for n in group}, {n1.pk, n2.pk})
        n2.refresh_from_db()
        self.assertEqual(n2.status, NominationStatus.APPROVED)
        self.assertEqual(n2.nominee_id, nominee.person_id)
        # Only one Person was created for the whole bundle, not one each.
        self.assertEqual(Person.objects.filter(display_name="Amira Hassan").count(), 1)

    def test_approving_reuses_an_already_linked_nominee(self):
        existing = make_person(display_name="Amira Hassan")
        nomination = make_nomination(nominee=existing)

        nominee, _ = approve(nomination, decided_by="cfo@example.com")

        self.assertEqual(nominee.person_id, existing.person_id)

    def test_approve_fires_nomination_approved_signal_once_per_bundle(self):
        received = []

        @receiver(nomination_approved)
        def _handler(sender, nomination, event, nominee, **kwargs):
            received.append(nominee.person_id)

        try:
            evt = make_event()
            n1 = make_nomination(event=evt, nominee_name="Amira Hassan")
            make_nomination(event=evt, nominee_name="Amira Hassan")
            approve(n1, decided_by="cfo@example.com")
        finally:
            nomination_approved.disconnect(_handler)

        self.assertEqual(len(received), 1)


class RejectAndWaitlistTests(TestCase):
    def test_reject_rejects_the_whole_bundle(self):
        event = make_event()
        n1 = make_nomination(event=event, nominee_name="Amira Hassan")
        n2 = make_nomination(event=event, nominee_name="Amira Hassan")

        reject(n1, decided_by="cfo@example.com")

        n2.refresh_from_db()
        self.assertEqual(n2.status, NominationStatus.REJECTED)

    def test_waitlist_sets_status(self):
        nomination = make_nomination(nominee_name="Amira Hassan")

        waitlist(nomination, decided_by="cfo@example.com")

        nomination.refresh_from_db()
        self.assertEqual(nomination.status, NominationStatus.WAITLISTED)


class BatchDecideTests(TestCase):
    def test_batch_decide_applies_mixed_actions(self):
        event = make_event()
        approve_me = make_nomination(event=event, nominee_name="Approve Me")
        reject_me = make_nomination(event=event, nominee_name="Reject Me")
        waitlist_me = make_nomination(event=event, nominee_name="Waitlist Me")

        decided_ids = batch_decide(
            [
                {"nomination_id": approve_me.pk, "action": "approve"},
                {"nomination_id": reject_me.pk, "action": "reject"},
                {"nomination_id": waitlist_me.pk, "action": "waitlist"},
            ],
            decided_by="cfo@example.com",
        )

        self.assertEqual(set(decided_ids), {approve_me.pk, reject_me.pk, waitlist_me.pk})
        approve_me.refresh_from_db()
        reject_me.refresh_from_db()
        waitlist_me.refresh_from_db()
        self.assertEqual(approve_me.status, NominationStatus.APPROVED)
        self.assertEqual(reject_me.status, NominationStatus.REJECTED)
        self.assertEqual(waitlist_me.status, NominationStatus.WAITLISTED)

    def test_batch_decide_skips_already_decided_nominations(self):
        nomination = make_nomination(nominee_name="Already Approved")
        approve(nomination, decided_by="cfo@example.com")

        decided_ids = batch_decide(
            [{"nomination_id": nomination.pk, "action": "reject"}], decided_by="ops@example.com"
        )

        self.assertEqual(decided_ids, [])
        nomination.refresh_from_db()
        self.assertEqual(nomination.status, NominationStatus.APPROVED)
