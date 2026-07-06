from django.test import TestCase
from django.utils import timezone
from people.tests.factories import make_person

from schedule.services.agenda import add_to_agenda, get_agenda, remove_from_agenda
from schedule.services.updates import delay
from schedule.tests.factories import make_room, make_session


class AgendaTests(TestCase):
    def test_add_and_get_agenda(self):
        person = make_person()
        session = make_session()

        add_to_agenda(person, session)

        self.assertEqual(get_agenda(person, session.event_id), [session])

    def test_adding_twice_is_idempotent(self):
        person = make_person()
        session = make_session()

        add_to_agenda(person, session)
        add_to_agenda(person, session)

        self.assertEqual(get_agenda(person, session.event_id), [session])

    def test_remove_from_agenda(self):
        person = make_person()
        session = make_session()
        add_to_agenda(person, session)

        remove_from_agenda(person, session)

        self.assertEqual(get_agenda(person, session.event_id), [])

    def test_agenda_reorders_automatically_when_a_session_is_delayed(self):
        person = make_person()
        room = make_room()
        now = timezone.now()
        early = make_session(room=room, title="Early", scheduled_start=now)
        late = make_session(room=room, title="Late", scheduled_start=now + timezone.timedelta(hours=1))
        add_to_agenda(person, early)
        add_to_agenda(person, late)

        # Delay "early" past "late" - the agenda should reflect the new order
        # without anyone touching the PersonalAgendaItem rows themselves.
        delay(early, 120, confirmed_by="ops@example.com")

        self.assertEqual(get_agenda(person, early.event_id), [late, early])
