from django.utils import timezone
from invitations.models import InvitationEventType
from invitations.tests.factories import make_invitation_event
from people.tests.factories import make_person
from rest_framework.test import APITestCase

from schedule.models import SessionStatus
from schedule.services.announcements import create_announcement
from schedule.tests.factories import make_room, make_session


class RoomStatusApiTests(APITestCase):
    def test_status_endpoint_requires_no_login_just_the_token(self):
        room = make_room()
        make_session(room=room, scheduled_start=timezone.now() - timezone.timedelta(minutes=5))

        response = self.client.get(f"/api/schedule/rooms/{room.update_token}/status/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.data["current_session"])

    def test_unknown_token_returns_404(self):
        import uuid

        response = self.client.get(f"/api/schedule/rooms/{uuid.uuid4()}/status/")
        self.assertEqual(response.status_code, 404)


class RoomUpdateApiTests(APITestCase):
    def test_delay_10_action(self):
        room = make_room()
        session = make_session(room=room, scheduled_start=timezone.now() - timezone.timedelta(minutes=5))

        response = self.client.post(
            f"/api/schedule/rooms/{room.update_token}/update/",
            {"action": "delay_10", "confirmed_by": "ops@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.status, SessionStatus.DELAYED)
        self.assertIn("suggested_shift_candidates", response.data)

    def test_apply_shift_endpoint(self):
        room = make_room()
        now = timezone.now()
        current = make_session(room=room, title="Now", scheduled_start=now - timezone.timedelta(minutes=5))
        later = make_session(room=room, title="Later", scheduled_start=now + timezone.timedelta(hours=1))

        response = self.client.post(
            f"/api/schedule/rooms/{room.update_token}/apply-shift/",
            {"session_ids": [later.pk], "minutes": 20, "confirmed_by": "ops@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        later.refresh_from_db()
        self.assertEqual(later.status, SessionStatus.DELAYED)


class AgendaApiTests(APITestCase):
    def test_add_and_list_agenda(self):
        person = make_person()
        session = make_session()

        add_response = self.client.post(
            "/api/schedule/agenda/", {"person": str(person.person_id), "session": session.pk}, format="json"
        )
        self.assertEqual(add_response.status_code, 200)

        list_response = self.client.get(
            f"/api/schedule/agenda/?person={person.person_id}&event={session.event_id}"
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data), 1)


class AttendeeSearchApiTests(APITestCase):
    def test_search_endpoint(self):
        from events.tests.factories import make_event

        event = make_event()
        person = make_person(display_name="Amira Hassan")
        make_invitation_event(person=person, event=event, event_type=InvitationEventType.ACCEPTED)

        response = self.client.get(f"/api/schedule/attendees/?event={event.pk}&q=amira")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)


class AnnouncementApiTests(APITestCase):
    def test_feed_endpoint_respects_audience(self):
        from events.tests.factories import make_event

        event = make_event()
        create_announcement(event, "General update.", created_by="staff@example.com")
        create_announcement(
            event, "Tech track only.", created_by="staff@example.com", audience_sector_tag="tech"
        )

        response = self.client.get(f"/api/schedule/announcements/feed/?event={event.pk}&sector=tech")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        general_only = self.client.get(f"/api/schedule/announcements/feed/?event={event.pk}")
        self.assertEqual(len(general_only.data), 1)
