from django.test import TestCase
from invitations.models import InvitationEventType
from invitations.tests.factories import make_invitation_event
from people.tests.factories import make_person

from seating.models import SeatPin, TableAssignment
from seating.services.assignments import run_full_optimization
from seating.services.pins import pin_seat, unpin_seat
from seating.tests.factories import make_table


class PinSeatTests(TestCase):
    def test_pin_creates_seat_pin_and_updates_assignment_immediately(self):
        table_a = make_table(name="A", capacity=4)
        table_b = make_table(event=table_a.event, name="B", capacity=4)
        person = make_person()

        pin_seat(table_a.event, person, table_b)

        self.assertEqual(SeatPin.objects.get(event=table_a.event, person=person).table, table_b)
        self.assertEqual(
            TableAssignment.objects.get(event=table_a.event, person=person).table, table_b
        )

    def test_pinning_clears_confirmation(self):
        table = make_table(capacity=4)
        person = make_person()
        make_invitation_event(person=person, event=table.event, event_type=InvitationEventType.ACCEPTED)
        run_full_optimization(table.event, iterations=50, seed=1)
        TableAssignment.objects.filter(event=table.event).update(is_confirmed=True)

        pin_seat(table.event, person, table)

        self.assertFalse(TableAssignment.objects.get(event=table.event, person=person).is_confirmed)

    def test_unpin_removes_the_pin(self):
        table = make_table(capacity=4)
        person = make_person()
        pin_seat(table.event, person, table)

        unpin_seat(table.event, person)

        self.assertFalse(SeatPin.objects.filter(event=table.event, person=person).exists())
