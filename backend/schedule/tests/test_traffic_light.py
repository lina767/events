from django.test import TestCase
from django.utils import timezone

from schedule.models import SessionStatus
from schedule.services.traffic_light import traffic_light
from schedule.tests.factories import make_session


class TrafficLightTests(TestCase):
    def test_recently_confirmed_is_green(self):
        session = make_session(last_confirmed_at=timezone.now(), status=SessionStatus.CONFIRMED)
        self.assertEqual(traffic_light(session).color, "green")

    def test_delayed_is_yellow(self):
        session = make_session(last_confirmed_at=timezone.now(), status=SessionStatus.DELAYED)
        self.assertEqual(traffic_light(session).color, "yellow")

    def test_never_confirmed_is_gray(self):
        session = make_session(last_confirmed_at=None)
        self.assertEqual(traffic_light(session).color, "gray")

    def test_stale_confirmation_degrades_to_gray_even_though_status_is_confirmed(self):
        stale = timezone.now() - timezone.timedelta(minutes=45)
        session = make_session(last_confirmed_at=stale, status=SessionStatus.CONFIRMED)
        self.assertEqual(traffic_light(session).color, "gray")

    def test_cancelled_overrides_everything(self):
        session = make_session(last_confirmed_at=timezone.now(), status=SessionStatus.CANCELLED)
        self.assertEqual(traffic_light(session).color, "cancelled")
