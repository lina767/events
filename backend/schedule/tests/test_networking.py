from django.test import TestCase
from events.tests.factories import make_event
from invitations.models import InvitationEventType
from invitations.tests.factories import make_invitation_event
from people.tests.factories import make_person

from schedule.services.networking import search_attendees


class SearchAttendeesTests(TestCase):
    def test_only_returns_accepted_attendees_of_the_given_event(self):
        event = make_event()
        accepted = make_person(display_name="Amira Hassan", organization="Acme Corp")
        make_invitation_event(person=accepted, event=event, event_type=InvitationEventType.ACCEPTED)

        invited_only = make_person(display_name="Jonas Weber")
        make_invitation_event(person=invited_only, event=event, event_type=InvitationEventType.INVITED)

        results = search_attendees(event)

        self.assertEqual(list(results), [accepted])

    def test_filters_by_name_or_organization(self):
        event = make_event()
        a = make_person(display_name="Amira Hassan", organization="Acme Corp")
        b = make_person(display_name="Jonas Weber", organization="Globex")
        for person in (a, b):
            make_invitation_event(person=person, event=event, event_type=InvitationEventType.ACCEPTED)

        self.assertEqual(list(search_attendees(event, query="amira")), [a])
        self.assertEqual(list(search_attendees(event, query="globex")), [b])

    def test_filters_by_sector_tag(self):
        event = make_event()
        tech = make_person(display_name="Amira Hassan", sector_tags=["tech"])
        finance = make_person(display_name="Jonas Weber", sector_tags=["finance"])
        for person in (tech, finance):
            make_invitation_event(person=person, event=event, event_type=InvitationEventType.ACCEPTED)

        self.assertEqual(list(search_attendees(event, sector_tag="tech")), [tech])
