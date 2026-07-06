"""
The honest-not-precise traffic light: a stale "on schedule" is more
dangerous than a visibly unclear one, since it looks certain when it
isn't - so silence past a threshold degrades the light instead of
leaving a stale time looking trustworthy.
"""

from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone

from schedule.models import Session, SessionStatus


@dataclass(frozen=True)
class TrafficLight:
    color: str  # "green" | "yellow" | "gray" | "cancelled"
    label: str


def traffic_light(session: Session) -> TrafficLight:
    if session.status == SessionStatus.CANCELLED:
        return TrafficLight("cancelled", "Cancelled")

    if session.status == SessionStatus.DELAYED:
        return TrafficLight("yellow", "Delayed, new estimated time shown")

    stale_minutes = settings.SCHEDULE_STALE_MINUTES
    if session.last_confirmed_at is None or (
        timezone.now() - session.last_confirmed_at
    ) > timezone.timedelta(minutes=stale_minutes):
        return TrafficLight("gray", f"Unconfirmed for over {stale_minutes} minutes")

    return TrafficLight("green", "Confirmed on time")
