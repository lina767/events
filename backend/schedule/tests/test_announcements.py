from django.test import TestCase
from events.tests.factories import make_event

from schedule.services.announcements import create_announcement, list_announcements


class AnnouncementTests(TestCase):
    def test_general_announcement_is_visible_to_everyone(self):
        event = make_event()
        create_announcement(event, "Doors open at 6pm.", created_by="staff@example.com")

        self.assertEqual(len(list_announcements(event)), 1)
        self.assertEqual(len(list_announcements(event, for_sector_tag="tech")), 1)

    def test_targeted_announcement_only_reaches_its_own_track(self):
        event = make_event()
        create_announcement(
            event, "Tech track moved to Room B.", created_by="staff@example.com", audience_sector_tag="tech"
        )

        self.assertEqual(len(list_announcements(event, for_sector_tag="tech")), 1)
        self.assertEqual(len(list_announcements(event, for_sector_tag="finance")), 0)
        self.assertEqual(len(list_announcements(event)), 0)

    def test_since_filters_out_older_announcements(self):
        from django.utils import timezone

        event = make_event()
        create_announcement(event, "Old news.", created_by="staff@example.com")
        cutoff = timezone.now()
        create_announcement(event, "Fresh news.", created_by="staff@example.com")

        recent = list_announcements(event, since=cutoff)

        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].message, "Fresh news.")
