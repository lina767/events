from decimal import Decimal

from django.db import models


class EventCategory(models.TextChoices):
    MAIN_CONFERENCE = "main_conference", "Main Conference"
    CURATED_SIDE_EVENT = "curated_side_event", "Curated Side Event"
    OTHER = "other", "Other"


class Event(models.Model):
    """
    Shared by the nominations and invitations modules: a main conference
    is typically mass-invited, a curated side event (e.g. a Chairmen's
    Dinner) is nomination-gated - both share the same capacity/overbooking
    math in the invitations app.
    """

    name = models.CharField(max_length=255)
    category = models.CharField(max_length=32, choices=EventCategory.choices)
    event_date = models.DateField()

    target_capacity = models.PositiveIntegerField(help_text="Actual number of seats.")
    historical_show_rate = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=Decimal("0.800"),
        help_text="Fraction of acceptances that historically actually show up.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-event_date"]

    def __str__(self):
        return self.name
