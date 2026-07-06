from events.tests.factories import make_event

from seating.models import RelationshipEdge, RelationshipType, SeatPin, Table


def make_table(event=None, name="Table 1", capacity=8, **kwargs) -> Table:
    return Table.objects.create(event=event or make_event(), name=name, capacity=capacity, **kwargs)


def make_relationship(person_a, person_b, edge_type=RelationshipType.POSITIVE, **kwargs) -> RelationshipEdge:
    return RelationshipEdge.objects.create(
        person_a=person_a, person_b=person_b, edge_type=edge_type, **kwargs
    )


def make_seat_pin(event, person, table) -> SeatPin:
    return SeatPin.objects.create(event=event, person=person, table=table)
