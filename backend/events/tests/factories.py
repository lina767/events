from decimal import Decimal

from events.models import Event, EventCategory


def make_event(name="Chairmen's Dinner", target_capacity=300, show_rate="0.800", **kwargs) -> Event:
    return Event.objects.create(
        name=name,
        category=kwargs.pop("category", EventCategory.CURATED_SIDE_EVENT),
        event_date=kwargs.pop("event_date", "2026-09-15"),
        target_capacity=target_capacity,
        historical_show_rate=Decimal(show_rate),
        **kwargs,
    )
