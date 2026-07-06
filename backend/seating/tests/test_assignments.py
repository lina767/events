from django.test import TestCase
from invitations.models import InvitationEventType
from invitations.tests.factories import make_invitation_event
from people.tests.factories import make_person

from seating.models import TableAssignment
from seating.services.assignments import (
    confirm_event_seating,
    run_full_optimization,
    run_local_reoptimization,
)
from seating.tests.factories import make_table


def _accepted_guest(event):
    person = make_person()
    make_invitation_event(person=person, event=event, event_type=InvitationEventType.ACCEPTED)
    return person


class RunFullOptimizationTests(TestCase):
    def test_seats_every_accepted_guest(self):
        table = make_table(capacity=10)
        guests = [_accepted_guest(table.event) for _ in range(6)]

        assignments = run_full_optimization(table.event, iterations=200, seed=1)

        self.assertEqual(len(assignments), 6)
        self.assertEqual(TableAssignment.objects.filter(event=table.event).count(), 6)

    def test_assignments_start_unconfirmed(self):
        table = make_table(capacity=10)
        _accepted_guest(table.event)

        assignments = run_full_optimization(table.event, iterations=50, seed=1)

        self.assertTrue(all(not a.is_confirmed for a in assignments))


class ConfirmEventSeatingTests(TestCase):
    def test_confirm_marks_all_pending_assignments(self):
        table = make_table(capacity=10)
        for _ in range(3):
            _accepted_guest(table.event)
        run_full_optimization(table.event, iterations=50, seed=1)

        count = confirm_event_seating(table.event, confirmed_by="ops@example.com")

        self.assertEqual(count, 3)
        self.assertTrue(
            all(a.is_confirmed for a in TableAssignment.objects.filter(event=table.event))
        )

    def test_a_new_optimization_run_reopens_confirmation(self):
        table = make_table(capacity=10)
        guests = [_accepted_guest(table.event) for _ in range(3)]
        run_full_optimization(table.event, iterations=50, seed=1)
        confirm_event_seating(table.event, confirmed_by="ops@example.com")

        run_local_reoptimization(table.event, [guests[0].person_id], iterations=50, seed=1)

        touched = TableAssignment.objects.get(event=table.event, person=guests[0])
        self.assertFalse(touched.is_confirmed)


class RunLocalReoptimizationTests(TestCase):
    def test_does_not_touch_every_table(self):
        """
        With 6 tables, a local reoptimization scopes to the touched table
        plus up to 2 neighbors - at most 3 tables. A global re-run would
        have no reason to leave any of the other 3 untouched.
        """
        event = make_table(name="A", capacity=2).event
        for name in ["B", "C", "D", "E", "F"]:
            make_table(event=event, name=name, capacity=2)
        guests = [_accepted_guest(event) for _ in range(12)]
        run_full_optimization(event, iterations=300, seed=3)

        before = {a.person_id: a.table_id for a in TableAssignment.objects.filter(event=event)}

        run_local_reoptimization(event, [guests[0].person_id], iterations=100, seed=3)

        after = {a.person_id: a.table_id for a in TableAssignment.objects.filter(event=event)}

        changed_tables = {before[pid] for pid in before if before[pid] != after[pid]} | {
            after[pid] for pid in after if before[pid] != after[pid]
        }
        self.assertLessEqual(len(changed_tables), 3)
        self.assertLess(len(changed_tables), 6)
