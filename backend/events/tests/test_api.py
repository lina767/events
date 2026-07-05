from rest_framework.test import APITestCase

from events.models import Event
from events.tests.factories import make_event


class EventApiTests(APITestCase):
    def test_create_event(self):
        response = self.client.post(
            "/api/events/",
            {
                "name": "Main Conference 2026",
                "category": "main_conference",
                "event_date": "2026-11-03",
                "target_capacity": 1200,
                "historical_show_rate": "0.85",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Event.objects.count(), 1)

    def test_list_events(self):
        make_event(name="Chairmen's Dinner")
        response = self.client.get("/api/events/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
