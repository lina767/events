from decimal import Decimal

from django.db import models

from events.models import Event
from people.models import Person


class Table(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="tables")
    name = models.CharField(max_length=100)
    capacity = models.PositiveIntegerField()

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["event", "name"], name="unique_table_name_per_event"),
        ]

    def __str__(self):
        return f"{self.name} ({self.event})"


class RelationshipType(models.TextChoices):
    POSITIVE = "positive", "Positive (should sit together)"
    NEGATIVE = "negative", "Conflict (must not sit together)"


class RelationshipEdge(models.Model):
    """
    A fact about two people, not about a specific event - "these two know
    each other" or "these two must not be seated together" holds across
    every dinner they both attend.
    """

    person_a = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="relationship_edges_as_a"
    )
    person_b = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="relationship_edges_as_b"
    )
    edge_type = models.CharField(max_length=16, choices=RelationshipType.choices)
    # Positive + hard = must sit together (e.g. a delegation/partner pair).
    # Negative is always effectively hard - a "soft conflict" isn't a conflict.
    is_hard_constraint = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["person_a", "person_b"], name="unique_relationship_pair"
            ),
            models.CheckConstraint(
                condition=~models.Q(person_a=models.F("person_b")), name="relationship_not_self"
            ),
        ]

    def __str__(self):
        symbol = "~" if self.edge_type == RelationshipType.POSITIVE else "x"
        return f"{self.person_a} {symbol} {self.person_b}"


class SeatPin(models.Model):
    """Manual, event-specific fixation - overrides the optimizer for this person only."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="seat_pins")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="seat_pins")
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name="seat_pins")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["event", "person"], name="one_pin_per_person_per_event"),
        ]

    def __str__(self):
        return f"{self.person} pinned to {self.table}"


class SeatingWeights(models.Model):
    """Per-event tuning of the three soft scoring criteria - equal by default."""

    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name="seating_weights")
    sector_diversity = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.00"))
    seniority_balance = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.00"))
    relationship_bonus = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("1.00"))

    def __str__(self):
        return f"Seating weights for {self.event}"


class TableAssignment(models.Model):
    """
    The current seating proposal, one active row per person per event.
    Never treated as final until confirm_event_seating() is called - no
    plan reaches guests without a human sign-off.
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="table_assignments")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="table_assignments")
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name="assignments")
    rationale = models.CharField(max_length=255, blank=True)
    is_confirmed = models.BooleanField(default=False)
    confirmed_by = models.CharField(max_length=255, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["event", "person"], name="one_assignment_per_person_per_event"
            ),
        ]

    def __str__(self):
        return f"{self.person} @ {self.table}"
