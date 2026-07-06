import uuid

from django.db import models

from events.models import Event
from people.models import Person


class Room(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=255)
    # The internal update page is keyed by this instead of a login: knowing
    # the (unguessable) token is the only credential it needs.
    update_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["event", "name"], name="unique_room_name_per_event"),
        ]

    def __str__(self):
        return f"{self.name} ({self.event})"


class SessionStatus(models.TextChoices):
    CONFIRMED = "confirmed", "Confirmed"
    DELAYED = "delayed", "Delayed"
    RUNNING = "running", "Running"
    CANCELLED = "cancelled", "Cancelled"


class Session(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="sessions")
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="sessions")
    title = models.CharField(max_length=255)
    speaker = models.CharField(max_length=255, blank=True)

    scheduled_start = models.DateTimeField()
    current_estimated_start = models.DateTimeField()
    status = models.CharField(
        max_length=16, choices=SessionStatus.choices, default=SessionStatus.CONFIRMED
    )
    last_confirmed_at = models.DateTimeField(null=True, blank=True)
    last_confirmed_by = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["room", "scheduled_start"]

    def __str__(self):
        return f"{self.title} @ {self.room}"

    def save(self, *args, **kwargs):
        if not self.current_estimated_start:
            self.current_estimated_start = self.scheduled_start
        super().save(*args, **kwargs)


class PersonalAgendaItem(models.Model):
    """
    Just a bookmark on an existing Session - a delay shows up in the
    participant's agenda automatically because it's the same row, not a
    copy that would need to be kept in sync.
    """

    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="agenda_items")
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="agenda_items")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["session__current_estimated_start"]
        constraints = [
            models.UniqueConstraint(fields=["person", "session"], name="unique_agenda_item"),
        ]

    def __str__(self):
        return f"{self.person} -> {self.session}"


class Announcement(models.Model):
    """A broadcast message, delivered by the same polling clients already use for the schedule."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="announcements")
    message = models.TextField()
    # Empty = everyone. Set = only participants tagged with this sector (e.g. one track).
    audience_sector_tag = models.CharField(max_length=100, blank=True)
    created_by = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.message[:60]
