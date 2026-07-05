from events.tests.factories import make_event
from nominations.models import NominationStatus
from nominations.tests.factories import make_nomination
from people.tests.factories import make_person
from rest_framework.test import APITestCase

from invitations.models import InvitationEventType
from invitations.tests.factories import make_invitation_event


class CapacityApiTests(APITestCase):
    def test_capacity_endpoint(self):
        event = make_event(target_capacity=100, show_rate="0.8")
        make_invitation_event(person=make_person(), event=event, event_type=InvitationEventType.ACCEPTED)

        response = self.client.get(f"/api/capacity/?event={event.pk}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["accepted_count"], 1)
        self.assertFalse(response.data["needs_promotion"])


class PromotionApiTests(APITestCase):
    def test_promotion_suggestions_endpoint(self):
        event = make_event()
        make_nomination(event=event, nominee_name="Amira Hassan", status=NominationStatus.WAITLISTED)

        response = self.client.get(f"/api/promotion-suggestions/?event={event.pk}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

    def test_promote_from_waitlist_endpoint(self):
        event = make_event()
        nomination = make_nomination(
            event=event, nominee_name="Amira Hassan", status=NominationStatus.WAITLISTED
        )

        response = self.client.post(
            "/api/invitation-events/promote-from-waitlist/",
            {"nomination_id": nomination.pk, "decided_by": "ops@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["event_type"], InvitationEventType.PROMOTED_FROM_WAITLIST)


class BulkImportApiTests(APITestCase):
    def test_bulk_import_endpoint(self):
        event = make_event()

        response = self.client.post(
            "/api/invitation-events/bulk-import/",
            {
                "event": event.pk,
                "rows": [{"name": "Amira Hassan", "email": "amira@example.com"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
