"""
Human-confirmed merge/reject/revert for DuplicateCandidate review.

There is no automatic merge path anywhere in this module - every call here
is triggered by an explicit human decision (see Modul 1 spec: a false
auto-merge on a VIP/diplomat record is riskier than a visible duplicate).
"""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from people.models import DuplicateCandidate, DuplicateCandidateStatus, Person, PersonMergeLog


class MergeError(Exception):
    pass


@transaction.atomic
def merge_persons(
    *,
    source: Person,
    target: Person,
    performed_by: str,
    rationale: str = "",
    confidence_score: int | None = None,
    duplicate_candidate: DuplicateCandidate | None = None,
) -> PersonMergeLog:
    """
    Merge `source` into `target`: reassign source's emails to target,
    deactivate source (person_id is kept, never deleted, so it stays a
    valid FK target for other modules), and log enough to revert.
    """
    if source.person_id == target.person_id:
        raise MergeError("Kann eine Person nicht mit sich selbst zusammenführen.")
    if not source.is_active:
        raise MergeError("Quelldatensatz ist bereits zusammengeführt/inaktiv.")
    if not target.is_active:
        raise MergeError("Zieldatensatz ist bereits zusammengeführt/inaktiv.")

    moved_emails = []
    target_has_primary = target.emails.filter(is_primary=True).exists()
    for email in source.emails.all():
        was_primary = email.is_primary
        moved_emails.append({"id": email.id, "was_primary": was_primary})
        email.person = target
        if was_primary and target_has_primary:
            email.is_primary = False
        email.save(update_fields=["person", "is_primary"])
        if was_primary and not target_has_primary:
            target_has_primary = True

    if source.last_verified_at and (
        target.last_verified_at is None or source.last_verified_at > target.last_verified_at
    ):
        target.last_verified_at = source.last_verified_at
        target.save(update_fields=["last_verified_at"])

    source.is_active = False
    source.merged_into = target
    source.save(update_fields=["is_active", "merged_into"])

    log = PersonMergeLog.objects.create(
        source_person=source,
        target_person=target,
        duplicate_candidate=duplicate_candidate,
        confidence_score=confidence_score,
        moved_emails=moved_emails,
        rationale=rationale,
        performed_by=performed_by,
    )

    if duplicate_candidate is not None:
        duplicate_candidate.status = DuplicateCandidateStatus.CONFIRMED
        duplicate_candidate.decided_at = timezone.now()
        duplicate_candidate.decided_by = performed_by
        duplicate_candidate.save(update_fields=["status", "decided_at", "decided_by"])

    # Any other still-open candidate involving the now-inactive source is
    # no longer a decision anyone needs to make.
    stale = DuplicateCandidate.objects.filter(
        Q(person_a=source) | Q(person_b=source),
        status=DuplicateCandidateStatus.PENDING,
    )
    if duplicate_candidate is not None:
        stale = stale.exclude(pk=duplicate_candidate.pk)
    stale.update(status=DuplicateCandidateStatus.OBSOLETE)

    return log


def reject_duplicate_candidate(
    candidate: DuplicateCandidate, performed_by: str
) -> DuplicateCandidate:
    """Human confirmed these are two different people - not a duplicate."""
    candidate.status = DuplicateCandidateStatus.REJECTED
    candidate.decided_at = timezone.now()
    candidate.decided_by = performed_by
    candidate.save(update_fields=["status", "decided_at", "decided_by"])
    return candidate


@transaction.atomic
def revert_merge(log: PersonMergeLog, performed_by: str) -> PersonMergeLog:
    """Undo a merge: move the recorded emails back, reactivate the source."""
    if log.is_reverted:
        raise MergeError("Diese Zusammenführung wurde bereits rückgängig gemacht.")

    source = log.source_person
    target = log.target_person

    for entry in log.moved_emails:
        email = target.emails.filter(id=entry["id"]).first()
        if email is None:
            continue
        email.person = source
        email.is_primary = entry["was_primary"]
        email.save(update_fields=["person", "is_primary"])

    source.is_active = True
    source.merged_into = None
    source.save(update_fields=["is_active", "merged_into"])

    log.reverted_at = timezone.now()
    log.reverted_by = performed_by
    log.save(update_fields=["reverted_at", "reverted_by"])

    if log.duplicate_candidate is not None:
        log.duplicate_candidate.status = DuplicateCandidateStatus.PENDING
        log.duplicate_candidate.decided_at = None
        log.duplicate_candidate.decided_by = ""
        log.duplicate_candidate.save(update_fields=["status", "decided_at", "decided_by"])

    return log
