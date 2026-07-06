"""
Overbooking-aware capacity math. Events are invited over target_capacity
on purpose (not everyone who accepts shows up), so a single decline isn't
automatically a "go fill the seat" signal - only a real shortfall is.
"""

from decimal import Decimal

from django.db.models import Max

from events.models import Event
from invitations.models import InvitationEvent, InvitationEventType
from people.models import Person


def current_status(person: Person, event: Event) -> str | None:
    """A person's status for an event is whatever their latest logged event says."""
    latest = InvitationEvent.objects.filter(person=person, event=event).order_by("-created_at", "-id").first()
    return latest.event_type if latest else None


def latest_invitation_event_ids(event: Event):
    """The id of each person's most recent InvitationEvent for this event."""
    return (
        InvitationEvent.objects.filter(event=event)
        .values("person")
        .annotate(latest_id=Max("id"))
        .values_list("latest_id", flat=True)
    )


def attendees_with_status(event: Event, statuses: list[str]):
    """Active Persons whose current status for this event is one of `statuses`."""
    person_ids = InvitationEvent.objects.filter(
        id__in=latest_invitation_event_ids(event), event_type__in=statuses
    ).values_list("person_id", flat=True)
    return Person.objects.filter(person_id__in=person_ids, is_active=True)


def accepted_attendees(event: Event):
    """Guests who have actually accepted - the pool schedule/networking and seating draw from."""
    return attendees_with_status(event, [InvitationEventType.ACCEPTED])


def accepted_count(event: Event) -> int:
    """How many people currently have ACCEPTED as their latest status."""
    return InvitationEvent.objects.filter(
        id__in=latest_invitation_event_ids(event), event_type=InvitationEventType.ACCEPTED
    ).count()


def expected_attendance(event: Event) -> Decimal:
    return Decimal(accepted_count(event)) * event.historical_show_rate


def buffer(event: Event) -> Decimal:
    """Seats left once the historical show rate is applied to current acceptances."""
    return Decimal(event.target_capacity) - expected_attendance(event)


def needs_promotion(event: Event, threshold: Decimal = Decimal("0")) -> bool:
    return buffer(event) < threshold
