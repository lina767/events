from django.dispatch import receiver

from nominations.signals import nomination_approved

from invitations.models import InvitationChannel, InvitationEvent, InvitationEventType


@receiver(nomination_approved)
def send_invitation_on_nomination_approval(sender, nomination, event, nominee, **kwargs):
    """
    Module 2 -> Module 3 handoff: an approved nomination becomes the
    nominee's first invitation record. Waitlist promotions are a separate,
    explicitly-confirmed path (see invitations.services.promotion) and
    don't go through this signal.
    """
    InvitationEvent.objects.create(
        person=nominee,
        event=event,
        event_type=InvitationEventType.INVITED,
        channel=InvitationChannel.NOMINATION,
        source_note=f"Approved nomination #{nomination.pk}",
    )
