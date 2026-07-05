from django.test import TestCase
from events.tests.factories import make_event
from nominations.services.decisions import approve
from nominations.tests.factories import make_nomination

from invitations.models import InvitationChannel, InvitationEvent, InvitationEventType


class NominationApprovalHandoffTests(TestCase):
    def test_approving_a_nomination_creates_an_invited_event(self):
        event = make_event()
        nomination = make_nomination(event=event, nominee_name="Amira Hassan")

        nominee, _ = approve(nomination, decided_by="cfo@example.com")

        invitation = InvitationEvent.objects.get(person=nominee, event=event)
        self.assertEqual(invitation.event_type, InvitationEventType.INVITED)
        self.assertEqual(invitation.channel, InvitationChannel.NOMINATION)

    def test_approving_a_bundle_only_sends_one_invitation(self):
        event = make_event()
        n1 = make_nomination(event=event, nominee_name="Amira Hassan")
        make_nomination(event=event, nominee_name="Amira Hassan")

        nominee, _ = approve(n1, decided_by="cfo@example.com")

        self.assertEqual(InvitationEvent.objects.filter(person=nominee, event=event).count(), 1)
