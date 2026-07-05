"""
Waitlist promotion: shows who's next, never sends anything by itself. A
misdirected invitation to the wrong VIP is politically sensitive, so a
human always confirms the specific promotion before it happens.
"""

from django.db import transaction
from django.utils import timezone

from nominations.models import Nomination, NominationStatus
from nominations.services.decisions import resolve_nominee

from invitations.models import InvitationChannel, InvitationEvent, InvitationEventType


def suggest_promotions(event, limit: int = 5) -> list[Nomination]:
    """Read-only: candidates the system surfaces, ordered by priority then submission time."""
    return list(
        Nomination.objects.filter(event=event, status=NominationStatus.WAITLISTED).order_by(
            "-priority", "created_at"
        )[:limit]
    )


@transaction.atomic
def promote_from_waitlist(nomination: Nomination, decided_by: str) -> InvitationEvent:
    nominee = resolve_nominee(nomination)
    nomination.nominee = nominee
    nomination.status = NominationStatus.APPROVED
    nomination.decided_at = timezone.now()
    nomination.decided_by = decided_by
    nomination.save(update_fields=["nominee", "status", "decided_at", "decided_by"])

    return InvitationEvent.objects.create(
        person=nominee,
        event=nomination.event,
        event_type=InvitationEventType.PROMOTED_FROM_WAITLIST,
        channel=InvitationChannel.MANUAL,
        source_note=f"Promoted from waitlist (nomination #{nomination.pk})",
    )
