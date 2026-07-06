from django.test import TestCase
from django.utils import timezone

from schedule.models import SessionStatus
from schedule.services.updates import (
    apply_shift_to_sessions,
    cancel,
    confirm_on_time,
    current_and_next_session,
    delay,
    mark_running,
    subsequent_sessions_in_room,
)
from schedule.tests.factories import make_room, make_session


class UpdateActionsTests(TestCase):
    def test_delay_shifts_estimated_start_and_stamps_confirmation(self):
        start = timezone.now()
        session = make_session(scheduled_start=start)

        delay(session, 10, confirmed_by="ops@example.com")

        session.refresh_from_db()
        self.assertEqual(session.status, SessionStatus.DELAYED)
        self.assertEqual(session.current_estimated_start, start + timezone.timedelta(minutes=10))
        self.assertEqual(session.last_confirmed_by, "ops@example.com")

    def test_confirm_on_time_resets_status(self):
        session = make_session(status=SessionStatus.DELAYED)

        confirm_on_time(session, confirmed_by="ops@example.com")

        session.refresh_from_db()
        self.assertEqual(session.status, SessionStatus.CONFIRMED)

    def test_mark_running_and_cancel(self):
        session = make_session()
        mark_running(session, confirmed_by="ops@example.com")
        session.refresh_from_db()
        self.assertEqual(session.status, SessionStatus.RUNNING)

        cancel(session, confirmed_by="ops@example.com")
        session.refresh_from_db()
        self.assertEqual(session.status, SessionStatus.CANCELLED)


class SubsequentSessionsAndShiftTests(TestCase):
    def test_subsequent_sessions_in_room_only_returns_later_ones(self):
        room = make_room()
        start = timezone.now()
        first = make_session(room=room, title="First", scheduled_start=start)
        second = make_session(
            room=room, title="Second", scheduled_start=start + timezone.timedelta(hours=1)
        )
        make_session(
            room=make_room(event=room.event, name="Other Room"),
            title="Different room",
            scheduled_start=start + timezone.timedelta(hours=1),
        )

        result = subsequent_sessions_in_room(first)

        self.assertEqual(result, [second])

    def test_apply_shift_delays_every_given_session(self):
        room = make_room()
        start = timezone.now()
        a = make_session(room=room, title="A", scheduled_start=start)
        b = make_session(room=room, title="B", scheduled_start=start + timezone.timedelta(hours=1))

        apply_shift_to_sessions([a, b], 15, confirmed_by="ops@example.com")

        a.refresh_from_db()
        b.refresh_from_db()
        self.assertEqual(a.status, SessionStatus.DELAYED)
        self.assertEqual(b.status, SessionStatus.DELAYED)


class CurrentAndNextSessionTests(TestCase):
    def test_running_session_wins_even_if_not_the_latest_started(self):
        room = make_room()
        now = timezone.now()
        make_session(room=room, title="Earlier", scheduled_start=now - timezone.timedelta(hours=2))
        running = make_session(
            room=room,
            title="Running",
            scheduled_start=now - timezone.timedelta(minutes=30),
            status=SessionStatus.RUNNING,
        )

        current, _ = current_and_next_session(room)

        self.assertEqual(current, running)

    def test_next_session_is_the_soonest_upcoming_one(self):
        room = make_room()
        now = timezone.now()
        current = make_session(
            room=room, title="Now", scheduled_start=now - timezone.timedelta(minutes=5)
        )
        soon = make_session(
            room=room, title="Soon", scheduled_start=now + timezone.timedelta(minutes=30)
        )
        make_session(room=room, title="Later", scheduled_start=now + timezone.timedelta(hours=2))

        _, next_session = current_and_next_session(room)

        self.assertEqual(next_session, soon)

    def test_cancelled_sessions_are_excluded(self):
        room = make_room()
        now = timezone.now()
        make_session(
            room=room,
            title="Cancelled",
            scheduled_start=now - timezone.timedelta(minutes=5),
            status=SessionStatus.CANCELLED,
        )

        current, _ = current_and_next_session(room)

        self.assertIsNone(current)
