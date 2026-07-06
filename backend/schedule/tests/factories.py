from django.utils import timezone
from events.tests.factories import make_event

from schedule.models import Room, Session


def make_room(event=None, name="Main Stage", **kwargs) -> Room:
    return Room.objects.create(event=event or make_event(), name=name, **kwargs)


def make_session(room=None, title="Opening Keynote", scheduled_start=None, **kwargs) -> Session:
    room = room or make_room()
    return Session.objects.create(
        event=kwargs.pop("event", room.event),
        room=room,
        title=title,
        scheduled_start=scheduled_start or timezone.now(),
        **kwargs,
    )
