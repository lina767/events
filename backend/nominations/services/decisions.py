"""
Human decisions on a nomination (or its whole duplicate-nominee bundle):
approve, reject, waitlist - individually for an urgent single case, or in
bulk for a scheduled decision round. Nothing here sends an invitation
itself; approving only resolves the nominee and fires nomination_approved
for the invitations module to act on.
"""

from django.db import transaction
from django.utils import timezone

from people.models import Person

from nominations.models import Nomination, NominationStatus
from nominations.services.bundling import find_group
from nominations.signals import nomination_approved


def resolve_nominee(nomination: Nomination) -> Person:
    """The linked Person if there is one, else a fresh Person from the free-text nominee."""
    if nomination.nominee_id:
        return nomination.nominee
    return Person.objects.create(
        display_name=nomination.nominee_name, organization=nomination.nominee_organization
    )


def _apply_to_group(group: list[Nomination], status: str, decided_by: str, nominee: Person | None = None):
    now = timezone.now()
    fields = ["status", "decided_at", "decided_by"]
    if nominee is not None:
        fields.append("nominee")
    for nomination in group:
        nomination.status = status
        nomination.decided_at = now
        nomination.decided_by = decided_by
        if nominee is not None:
            nomination.nominee = nominee
        nomination.save(update_fields=fields)


@transaction.atomic
def approve(nomination: Nomination, decided_by: str) -> tuple[Person, list[Nomination]]:
    """
    Approve a nomination and every other open nomination for the same
    nominee. If nobody in the bundle is linked to a Golden Record Person
    yet, create one from the nominee's name/organization - this runs
    through Person's normal creation path, so Module 1's duplicate
    detection fires automatically.
    """
    group = find_group(nomination)
    resolved_nominee = next((n.nominee for n in group if n.nominee_id), None) or resolve_nominee(
        nomination
    )
    _apply_to_group(group, NominationStatus.APPROVED, decided_by, nominee=resolved_nominee)
    nomination_approved.send(
        sender=Nomination, nomination=nomination, event=nomination.event, nominee=resolved_nominee
    )
    return resolved_nominee, group


@transaction.atomic
def reject(nomination: Nomination, decided_by: str) -> list[Nomination]:
    group = find_group(nomination)
    _apply_to_group(group, NominationStatus.REJECTED, decided_by)
    return group


@transaction.atomic
def waitlist(nomination: Nomination, decided_by: str) -> list[Nomination]:
    group = find_group(nomination)
    _apply_to_group(group, NominationStatus.WAITLISTED, decided_by)
    return group


_ACTIONS = {"approve": approve, "reject": reject, "waitlist": waitlist}


def batch_decide(decisions: list[dict], decided_by: str) -> list[int]:
    """
    The "Sammelrunde" batch-review mode: apply a list of
    {"nomination_id": int, "action": "approve"|"reject"|"waitlist"}
    decisions in one pass, e.g. right before a nomination deadline.
    """
    decided_ids = []
    for decision in decisions:
        action = _ACTIONS.get(decision["action"])
        if action is None:
            continue
        try:
            nomination = Nomination.objects.get(
                pk=decision["nomination_id"], status=NominationStatus.OPEN
            )
        except Nomination.DoesNotExist:
            continue
        action(nomination, decided_by)
        decided_ids.append(nomination.pk)
    return decided_ids
