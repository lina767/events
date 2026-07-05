from decimal import Decimal

from django.test import TestCase
from events.tests.factories import make_event
from people.tests.factories import make_person

from invitations.models import InvitationEventType
from invitations.services.capacity import accepted_count, buffer, current_status, needs_promotion
from invitations.tests.factories import make_invitation_event


class CurrentStatusTests(TestCase):
    def test_status_is_the_latest_event(self):
        event = make_event()
        person = make_person()
        make_invitation_event(person=person, event=event, event_type=InvitationEventType.INVITED)
        make_invitation_event(person=person, event=event, event_type=InvitationEventType.ACCEPTED)
        make_invitation_event(person=person, event=event, event_type=InvitationEventType.DECLINED)

        self.assertEqual(current_status(person, event), InvitationEventType.DECLINED)

    def test_status_is_none_without_any_events(self):
        event = make_event()
        person = make_person()
        self.assertIsNone(current_status(person, event))


class CapacityTests(TestCase):
    def test_accepted_count_only_counts_current_acceptances(self):
        event = make_event(target_capacity=100, show_rate="0.8")
        p1, p2, p3 = make_person(), make_person(), make_person()
        make_invitation_event(person=p1, event=event, event_type=InvitationEventType.ACCEPTED)
        make_invitation_event(person=p2, event=event, event_type=InvitationEventType.ACCEPTED)
        make_invitation_event(person=p3, event=event, event_type=InvitationEventType.ACCEPTED)
        # p2 later declines - should no longer count as accepted.
        make_invitation_event(person=p2, event=event, event_type=InvitationEventType.DECLINED)

        self.assertEqual(accepted_count(event), 2)

    def test_buffer_applies_historical_show_rate(self):
        event = make_event(target_capacity=100, show_rate="0.800")
        for _ in range(10):
            make_invitation_event(
                person=make_person(), event=event, event_type=InvitationEventType.ACCEPTED
            )

        # 10 accepted * 0.8 show rate = 8 expected attendees, 100 - 8 = 92 buffer.
        self.assertEqual(buffer(event), Decimal("92.000"))

    def test_needs_promotion_when_buffer_below_threshold(self):
        event = make_event(target_capacity=7, show_rate="1.000")
        for _ in range(8):
            make_invitation_event(
                person=make_person(), event=event, event_type=InvitationEventType.ACCEPTED
            )

        # 8 accepted * 1.0 show rate = 8 expected, but only 7 seats -> shortfall.
        self.assertTrue(needs_promotion(event))

    def test_no_promotion_needed_while_overbooking_buffer_holds(self):
        event = make_event(target_capacity=100, show_rate="0.5")
        for _ in range(10):
            make_invitation_event(
                person=make_person(), event=event, event_type=InvitationEventType.ACCEPTED
            )

        # 10 accepted * 0.5 = 5 expected, buffer = 95 - well above the threshold.
        self.assertFalse(needs_promotion(event))
