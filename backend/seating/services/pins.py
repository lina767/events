from django.db import transaction

from seating.models import SeatPin, TableAssignment


@transaction.atomic
def pin_seat(event, person, table) -> SeatPin:
    """
    Manually fixes a person's table - the optimizer respects this on every
    future run. The current assignment is updated immediately (and its
    confirmation cleared, since the seating just changed) so the move is
    visible right away instead of waiting for the next optimization pass.
    """
    pin, _created = SeatPin.objects.update_or_create(
        event=event, person=person, defaults={"table": table}
    )
    TableAssignment.objects.update_or_create(
        event=event,
        person=person,
        defaults={
            "table": table,
            "rationale": "Manually pinned",
            "is_confirmed": False,
            "confirmed_by": "",
            "confirmed_at": None,
        },
    )
    return pin


def unpin_seat(event, person) -> None:
    SeatPin.objects.filter(event=event, person=person).delete()
