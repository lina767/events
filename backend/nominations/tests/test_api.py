from events.tests.factories import make_event
from people.tests.factories import make_person
from rest_framework.test import APITestCase

from nominations.models import Nomination, NominationStatus
from nominations.tests.factories import make_nomination


class NominationApiTests(APITestCase):
    def test_create_requires_nominee_or_nominee_name(self):
        event = make_event()
        nominator = make_person(display_name="Staff Member")

        response = self.client.post(
            "/api/nominations/",
            {"event": event.pk, "nominator": str(nominator.person_id)},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_create_with_nominee_name(self):
        event = make_event()
        nominator = make_person(display_name="Staff Member")

        response = self.client.post(
            "/api/nominations/",
            {
                "event": event.pk,
                "nominator": str(nominator.person_id),
                "nominee_name": "Amira Hassan",
                "rationale": "Met at Davos, strong sector fit.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Nomination.objects.count(), 1)

    def test_approve_endpoint_approves_the_bundle(self):
        event = make_event()
        n1 = make_nomination(event=event, nominee_name="Amira Hassan")
        n2 = make_nomination(event=event, nominee_name="Amira Hassan")

        response = self.client.post(
            f"/api/nominations/{n1.pk}/approve/", {"decided_by": "cfo@example.com"}, format="json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        n2.refresh_from_db()
        self.assertEqual(n2.status, NominationStatus.APPROVED)

    def test_grouped_pending_endpoint(self):
        event = make_event()
        make_nomination(event=event, nominee_name="Amira Hassan")
        make_nomination(event=event, nominee_name="Amira Hassan")
        make_nomination(event=event, nominee_name="Someone Else")

        response = self.client.get(f"/api/nominations/grouped-pending/?event={event.pk}")

        self.assertEqual(response.status_code, 200)
        sizes = sorted(len(group["nominations"]) for group in response.data)
        self.assertEqual(sizes, [1, 2])

    def test_batch_decide_endpoint(self):
        event = make_event()
        n1 = make_nomination(event=event, nominee_name="Approve Me")
        n2 = make_nomination(event=event, nominee_name="Reject Me")

        response = self.client.post(
            "/api/nominations/batch-decide/",
            {
                "decided_by": "cfo@example.com",
                "decisions": [
                    {"nomination_id": n1.pk, "action": "approve"},
                    {"nomination_id": n2.pk, "action": "reject"},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.data["decided_ids"]), {n1.pk, n2.pk})
