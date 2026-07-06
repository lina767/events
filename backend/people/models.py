import re
import unicodedata
import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone


def normalize_name(name: str) -> str:
    """Lowercase, strip diacritics/punctuation, collapse whitespace - for matching only."""
    if not name:
        return ""
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    ascii_only = ascii_only.lower()
    ascii_only = re.sub(r"[^a-z0-9\s]", " ", ascii_only)
    return re.sub(r"\s+", " ", ascii_only).strip()


class ConsentStatus(models.TextChoices):
    GIVEN = "given", "Given"
    REVOKED = "revoked", "Revoked"
    UNCLEAR = "unclear", "Unclear"


class SeniorityLevel(models.TextChoices):
    C_LEVEL = "c_level", "C-Level"
    SENIOR_EXECUTIVE = "senior_executive", "Senior Executive"
    MANAGEMENT = "management", "Management"
    STAFF = "staff", "Staff"
    OTHER = "other", "Other"


class Person(models.Model):
    """
    Golden Record: the single, stable identity every other module refers to
    via person_id. person_id is never edited; merges deactivate the losing
    record rather than deleting it, so the id stays a stable foreign key
    target even after a merge (see PersonMergeLog for revert support).
    """

    person_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    display_name = models.CharField(max_length=255)
    normalized_name = models.CharField(max_length=255, editable=False, db_index=True)

    organization = models.CharField(max_length=255, blank=True)
    sector_tags = ArrayField(
        models.CharField(max_length=100), blank=True, default=list
    )
    seniority_level = models.CharField(
        max_length=32, choices=SeniorityLevel.choices, blank=True
    )

    last_verified_at = models.DateTimeField(null=True, blank=True)
    consent_status = models.CharField(
        max_length=16, choices=ConsentStatus.choices, default=ConsentStatus.UNCLEAR
    )
    data_retention_note = models.TextField(blank=True)

    # A merged-away record stays in the table (person_id must remain a
    # stable FK target for other modules / historical InvitationEvents),
    # it just becomes inactive and points at the surviving record.
    is_active = models.BooleanField(default=True)
    merged_into = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="absorbed_persons",
    )
    flagged_for_review = models.BooleanField(default=False)

    # Set once a deletion request has been executed (see PersonDeletionLog).
    # The row survives as a tombstone - other modules' FKs to person_id must
    # keep resolving - but its personal data has been scrubbed.
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(merged_into=models.F("person_id")),
                name="person_cannot_merge_into_self",
            ),
        ]

    def __str__(self):
        return self.display_name

    def save(self, *args, **kwargs):
        self.normalized_name = normalize_name(self.display_name)
        super().save(*args, **kwargs)

    def is_stale(self, months: int) -> bool:
        if self.last_verified_at is None:
            return True
        threshold = timezone.now() - timezone.timedelta(days=months * 30)
        return self.last_verified_at < threshold

    @property
    def primary_email(self):
        return self.emails.filter(is_primary=True).first()


class PersonEmail(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="emails")
    email = models.EmailField()
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["email"], name="unique_person_email"),
            models.UniqueConstraint(
                fields=["person"],
                condition=models.Q(is_primary=True),
                name="one_primary_email_per_person",
            ),
        ]
        ordering = ["-is_primary", "email"]

    def __str__(self):
        return self.email

    @property
    def domain(self) -> str:
        return self.email.rsplit("@", 1)[-1].lower() if "@" in self.email else ""


class DuplicateCandidateStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed (merged)"
    REJECTED = "rejected", "Rejected (not a duplicate)"
    OBSOLETE = "obsolete", "Obsolete"


class DuplicateCandidate(models.Model):
    """
    A suggested duplicate pair awaiting human review. Never auto-merged -
    a false-positive merge on a VIP record is worse than a visible duplicate.
    """

    person_a = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="duplicate_candidates_as_a"
    )
    person_b = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name="duplicate_candidates_as_b"
    )
    confidence_score = models.PositiveSmallIntegerField()
    reasons = ArrayField(models.CharField(max_length=255), default=list)
    status = models.CharField(
        max_length=16,
        choices=DuplicateCandidateStatus.choices,
        default=DuplicateCandidateStatus.PENDING,
    )
    detected_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-confidence_score", "-detected_at"]
        verbose_name_plural = "Duplicates"
        constraints = [
            models.UniqueConstraint(
                fields=["person_a", "person_b"], name="unique_duplicate_pair"
            ),
        ]

    def __str__(self):
        return f"{self.person_a} <-> {self.person_b} ({self.confidence_score}%)"


class PersonMergeLog(models.Model):
    """
    Audit trail of merges, precise enough to revert one: we never delete
    PersonEmail rows on merge, only reassign them, so a revert just moves
    the recorded email ids back and reactivates the source person.
    """

    source_person = models.ForeignKey(
        Person, on_delete=models.PROTECT, related_name="merge_log_as_source"
    )
    target_person = models.ForeignKey(
        Person, on_delete=models.PROTECT, related_name="merge_log_as_target"
    )
    duplicate_candidate = models.ForeignKey(
        DuplicateCandidate, null=True, blank=True, on_delete=models.SET_NULL
    )
    confidence_score = models.PositiveSmallIntegerField(null=True, blank=True)
    # [{"id": <PersonEmail.id>, "was_primary": bool}, ...] - precise enough
    # to move emails back to the source person and restore is_primary on revert.
    moved_emails = models.JSONField(default=list)
    rationale = models.TextField(blank=True)
    performed_by = models.CharField(max_length=255, blank=True)
    performed_at = models.DateTimeField(auto_now_add=True)
    reverted_at = models.DateTimeField(null=True, blank=True)
    reverted_by = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-performed_at"]
        verbose_name_plural = "Merge log"

    def __str__(self):
        return f"Merge {self.source_person_id} -> {self.target_person_id}"

    @property
    def is_reverted(self) -> bool:
        return self.reverted_at is not None


class PersonDeletionLog(models.Model):
    """
    Audit trail for executed erasure requests. The Person row is never
    hard-deleted - person_id must stay a stable FK target for every other
    module's historical records - it's anonymized in place, and this log
    is what makes that anonymization accountable: who asked, who did it,
    when, and the documented retention/deletion rationale the privacy
    section of the spec requires instead of "we never cleaned up."
    """

    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="deletion_logs")
    requested_by = models.CharField(
        max_length=255, blank=True, help_text="The data subject, or whoever raised the request."
    )
    performed_by = models.CharField(max_length=255)
    reason = models.TextField(blank=True)
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-performed_at"]
        verbose_name_plural = "Deletion log"

    def __str__(self):
        return f"Deletion of {self.person_id} by {self.performed_by}"
