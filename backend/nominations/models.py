from django.db import models

from events.models import Event
from people.models import Person


class NominationStatus(models.TextChoices):
    OPEN = "open", "Open"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"
    WAITLISTED = "waitlisted", "Waitlisted"


class Nomination(models.Model):
    """
    A staff member's proposal to invite someone to an event. The nominee
    may already be a Golden Record Person, or a brand-new contact (name +
    organization only) that becomes a Person only once approved - see
    nominations.services.decisions.approve().
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="nominations")
    nominator = models.ForeignKey(
        Person, on_delete=models.PROTECT, related_name="nominations_made"
    )
    nominee = models.ForeignKey(
        Person,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="nominations_received",
    )
    nominee_name = models.CharField(
        max_length=255, blank=True, help_text="Used when the nominee isn't a Person yet."
    )
    nominee_organization = models.CharField(max_length=255, blank=True)

    rationale = models.TextField(blank=True)
    status = models.CharField(
        max_length=16, choices=NominationStatus.choices, default=NominationStatus.OPEN
    )
    # Manual override for waitlist ordering; ties broken by submission time.
    priority = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-priority", "created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(nominee__isnull=False) | ~models.Q(nominee_name=""),
                name="nomination_has_a_nominee_or_a_name",
            ),
        ]

    def __str__(self):
        who = self.nominee.display_name if self.nominee_id else self.nominee_name
        return f"{who} for {self.event} (by {self.nominator})"

    @property
    def nominee_display_name(self) -> str:
        return self.nominee.display_name if self.nominee_id else self.nominee_name
