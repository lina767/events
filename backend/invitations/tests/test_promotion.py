from django.test import TestCase
from events.tests.factories import make_event
from nominations.models import NominationStatus
from nominations.tests.factories import make_nomination
from people.models import Person

from invitations.models import InvitationEventType
from invitations.services.promotion import promote_from_waitlist, suggest_promotions


class SuggestPromotionsTests(TestCase):
    def test_orders_by_priority_then_submission_time(self):
        event = make_event()
        low = make_nomination(event=event, nominee_name="Low Priority", status=NominationStatus.WAITLISTED, priority=0)
        high = make_nomination(event=event, nominee_name="High Priority", status=NominationStatus.WAITLISTED, priority=10)

        suggestions = suggest_promotions(event)

        self.assertEqual(suggestions, [high, low])

    def test_excludes_non_waitlisted_nominations(self):
        event = make_event()
        make_nomination(event=event, nominee_name="Still Open")

        self.assertEqual(suggest_promotions(event), [])


class PromoteFromWaitlistTests(TestCase):
    def test_promotion_creates_invitation_and_approves_nomination(self):
        event = make_event()
        nomination = make_nomination(
            event=event, nominee_name="Amira Hassan", status=NominationStatus.WAITLISTED
        )

        invitation = promote_from_waitlist(nomination, decided_by="ops@example.com")

        self.assertEqual(invitation.event_type, InvitationEventType.PROMOTED_FROM_WAITLIST)
        nomination.refresh_from_db()
        self.assertEqual(nomination.status, NominationStatus.APPROVED)
        self.assertTrue(Person.objects.filter(display_name="Amira Hassan").exists())

    def test_promotion_reuses_existing_nominee(self):
        from people.tests.factories import make_person

        existing = make_person(display_name="Amira Hassan")
        nomination = make_nomination(nominee=existing, status=NominationStatus.WAITLISTED)

        invitation = promote_from_waitlist(nomination, decided_by="ops@example.com")

        self.assertEqual(invitation.person_id, existing.person_id)
