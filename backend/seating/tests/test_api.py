from invitations.models import InvitationEventType
from invitations.tests.factories import make_invitation_event
from people.tests.factories import make_person
from rest_framework.test import APITestCase

from seating.models import RelationshipEdge, TableAssignment
from seating.tests.factories import make_table


def _accepted_guest(event):
    person = make_person()
    make_invitation_event(person=person, event=event, event_type=InvitationEventType.ACCEPTED)
    return person


class OptimizeApiTests(APITestCase):
    def test_optimize_endpoint_seats_guests(self):
        table = make_table(capacity=10)
        for _ in range(4):
            _accepted_guest(table.event)

        response = self.client.post(
            "/api/seating/assignments/optimize/",
            {"event": table.event.pk, "iterations": 100, "seed": 1},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 4)

    def test_confirm_endpoint(self):
        table = make_table(capacity=10)
        _accepted_guest(table.event)
        self.client.post(
            "/api/seating/assignments/optimize/",
            {"event": table.event.pk, "iterations": 50, "seed": 1},
            format="json",
        )

        response = self.client.post(
            "/api/seating/assignments/confirm/",
            {"event": table.event.pk, "confirmed_by": "ops@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["confirmed_count"], 1)


class PinApiTests(APITestCase):
    def test_pin_endpoint(self):
        table_a = make_table(name="A", capacity=4)
        table_b = make_table(event=table_a.event, name="B", capacity=4)
        person = make_person()

        response = self.client.post(
            "/api/seating/assignments/pin/",
            {"event": table_a.event.pk, "person": str(person.person_id), "table": table_b.pk},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            TableAssignment.objects.get(event=table_a.event, person=person).table_id, table_b.pk
        )


class RelationshipEdgeApiTests(APITestCase):
    def test_create_relationship_edge(self):
        a, b = make_person(), make_person()

        response = self.client.post(
            "/api/seating/relationship-edges/",
            {"person_a": str(a.person_id), "person_b": str(b.person_id), "edge_type": "positive"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(RelationshipEdge.objects.count(), 1)
