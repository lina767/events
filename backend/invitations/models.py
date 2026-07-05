from django.db import models

from events.models import Event
from people.models import Person


class InvitationEventType(models.TextChoices):
    INVITED = "invited", "Invited"
    ACCEPTED = "accepted", "Accepted"
    DECLINED = "declined", "Declined"
    PROMOTED_FROM_WAITLIST = "promoted_from_waitlist", "Promoted from waitlist"
    NO_SHOW = "no_show", "No-show"


class InvitationChannel(models.TextChoices):
    PLATFORM = "platform", "Self-service platform"
    EMAIL = "email", "Email"
    MANUAL = "manual", "Manual"
    EXCEL_IMPORT = "excel_import", "Excel import"
    NOMINATION = "nomination", "Nomination approval"


class InvitationEvent(models.Model):
    """
    Append-only status log. A person's current status for an event is
    never stored as an editable field - it's derived from the latest row
    here, so the full history (invited -> accepted -> declined last
    minute) survives instead of being overwritten.
    """

    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="invitation_events")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="invitation_events")
    event_type = models.CharField(max_length=32, choices=InvitationEventType.choices)
    channel = models.CharField(max_length=16, choices=InvitationChannel.choices)
    source_note = models.TextField(blank=True)

    # For matching an inbound email reply back to the invitation it answers.
    tracking_code = models.CharField(max_length=64, blank=True, db_index=True)
    conversation_id = models.CharField(max_length=255, blank=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.person} - {self.get_event_type_display()} @ {self.event}"


class EmailClassification(models.TextChoices):
    ACCEPTED = "accepted", "Accepted"
    DECLINED = "declined", "Declined"
    AMBIGUOUS = "ambiguous", "Ambiguous (needs review)"


class EmailReply(models.Model):
    """
    Every inbound reply this system parsed, whether or not it could be
    classified unambiguously. This is the integration point a Microsoft
    Graph webhook handler would call after fetching a message's body -
    this app does not talk to Graph itself (no tenant credentials here).
    """

    event = models.ForeignKey(
        Event, null=True, blank=True, on_delete=models.SET_NULL, related_name="email_replies"
    )
    person = models.ForeignKey(
        Person, null=True, blank=True, on_delete=models.SET_NULL, related_name="email_replies"
    )
    tracking_code = models.CharField(max_length=64, blank=True)
    conversation_id = models.CharField(max_length=255, blank=True, db_index=True)
    raw_body = models.TextField()
    received_at = models.DateTimeField()
    classification = models.CharField(max_length=16, choices=EmailClassification.choices)
    resulting_invitation_event = models.ForeignKey(
        InvitationEvent, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    resolved_by = models.CharField(max_length=255, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-received_at"]
        verbose_name_plural = "Email replies"

    def __str__(self):
        return f"Reply from {self.person or 'unknown'} ({self.classification})"

    @property
    def needs_review(self) -> bool:
        return self.resulting_invitation_event_id is None


class StandbyContact(models.Model):
    """
    The day-of-event escalation list for very last-minute cancellations,
    where an email round-trip is too slow. Deliberately not automated -
    this just makes the list visible; calling people is a manual,
    on-the-ground process.
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="standby_contacts")
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=64)
    notes = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"{self.name} ({self.event})"
