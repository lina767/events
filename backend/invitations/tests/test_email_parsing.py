from django.test import TestCase
from django.utils import timezone
from events.tests.factories import make_event
from people.tests.factories import make_person

from invitations.models import EmailClassification, InvitationEventType
from invitations.services.email_parsing import classify_reply, record_email_reply, resolve_ambiguous_reply
from invitations.tests.factories import make_invitation_event


class ClassifyReplyTests(TestCase):
    def test_english_acceptance(self):
        self.assertEqual(classify_reply("Yes, I'll be attending, looking forward to it!"), EmailClassification.ACCEPTED)

    def test_german_acceptance(self):
        self.assertEqual(classify_reply("Vielen Dank, ich sage gerne zu."), EmailClassification.ACCEPTED)

    def test_english_decline(self):
        self.assertEqual(classify_reply("Sorry, I cannot attend this year."), EmailClassification.DECLINED)

    def test_german_decline(self):
        self.assertEqual(classify_reply("Leider kann ich an diesem Termin nicht teilnehmen."), EmailClassification.DECLINED)

    def test_ambiguous_when_unclear(self):
        self.assertEqual(classify_reply("Can you send me the agenda for the day?"), EmailClassification.AMBIGUOUS)


class RecordEmailReplyTests(TestCase):
    def test_matches_by_tracking_code_and_creates_invitation_event(self):
        event = make_event()
        person = make_person()
        make_invitation_event(
            person=person, event=event, event_type=InvitationEventType.INVITED, tracking_code="abc123"
        )

        reply = record_email_reply(
            body="Yes, gladly attending!", received_at=timezone.now(), tracking_code="abc123"
        )

        self.assertEqual(reply.classification, EmailClassification.ACCEPTED)
        self.assertIsNotNone(reply.resulting_invitation_event)
        self.assertEqual(reply.resulting_invitation_event.event_type, InvitationEventType.ACCEPTED)
        self.assertFalse(reply.needs_review)

    def test_conversation_id_takes_priority_over_tracking_code(self):
        event = make_event()
        person = make_person()
        make_invitation_event(
            person=person,
            event=event,
            event_type=InvitationEventType.INVITED,
            tracking_code="stale-code",
            conversation_id="conv-1",
        )

        reply = record_email_reply(
            body="Leider kann ich nicht kommen.",
            received_at=timezone.now(),
            tracking_code="wrong-code",
            conversation_id="conv-1",
        )

        self.assertEqual(reply.person_id, person.person_id)
        self.assertEqual(reply.resulting_invitation_event.event_type, InvitationEventType.DECLINED)

    def test_ambiguous_reply_does_not_create_an_invitation_event(self):
        event = make_event()
        person = make_person()
        make_invitation_event(
            person=person, event=event, event_type=InvitationEventType.INVITED, tracking_code="abc123"
        )

        reply = record_email_reply(
            body="What time does the dinner start?", received_at=timezone.now(), tracking_code="abc123"
        )

        self.assertEqual(reply.classification, EmailClassification.AMBIGUOUS)
        self.assertIsNone(reply.resulting_invitation_event)
        self.assertTrue(reply.needs_review)

    def test_unmatched_reply_is_logged_without_invitation_event(self):
        reply = record_email_reply(body="Yes, of course!", received_at=timezone.now(), tracking_code="unknown")

        self.assertIsNone(reply.person)
        self.assertIsNone(reply.resulting_invitation_event)


class ResolveAmbiguousReplyTests(TestCase):
    def test_manual_resolution_creates_invitation_event(self):
        event = make_event()
        person = make_person()
        make_invitation_event(
            person=person, event=event, event_type=InvitationEventType.INVITED, tracking_code="abc123"
        )
        reply = record_email_reply(
            body="Let me get back to you.", received_at=timezone.now(), tracking_code="abc123"
        )

        invitation = resolve_ambiguous_reply(reply, "accepted", resolved_by="ops@example.com")

        self.assertEqual(invitation.event_type, InvitationEventType.ACCEPTED)
        reply.refresh_from_db()
        self.assertFalse(reply.needs_review)
        self.assertEqual(reply.resolved_by, "ops@example.com")

    def test_cannot_resolve_a_reply_with_no_match(self):
        reply = record_email_reply(body="Sure!", received_at=timezone.now())

        with self.assertRaises(ValueError):
            resolve_ambiguous_reply(reply, "accepted", resolved_by="ops@example.com")
