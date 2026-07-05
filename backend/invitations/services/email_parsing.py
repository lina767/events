"""
Classifies inbound reply emails and matches them back to the invitation
they answer. This is the logic a Microsoft Graph webhook handler would
call after fetching a message's body via Mail.Read - this module never
talks to Graph itself (no Azure AD app registration/tenant credentials
exist in this environment), it only does the parsing/matching Graph
would trigger.

Guests reply in whatever language they write in day to day, regardless
of the platform's own UI language, so keyword matching covers English
and German.
"""

from django.utils import timezone

from invitations.models import (
    EmailClassification,
    EmailReply,
    InvitationChannel,
    InvitationEvent,
    InvitationEventType,
)

ACCEPT_KEYWORDS = [
    "yes", "accept", "attending", "will attend", "gladly", "pleased to", "confirm", "looking forward",
    "zusage", "gerne", "ich komme", "nehme teil", "sage zu", "freue mich",
]

DECLINE_KEYWORDS = [
    "no,", "decline", "cannot attend", "can't attend", "unable to attend", "regret", "sorry, i", "won't be able",
    "absage", "leider", "kann nicht", "kann leider nicht", "sage ab",
]


def classify_reply(text: str) -> str:
    normalized = text.lower()
    accepted = any(keyword in normalized for keyword in ACCEPT_KEYWORDS)
    declined = any(keyword in normalized for keyword in DECLINE_KEYWORDS)
    if accepted and not declined:
        return EmailClassification.ACCEPTED
    if declined and not accepted:
        return EmailClassification.DECLINED
    return EmailClassification.AMBIGUOUS


def _resolve_person_and_event(tracking_code: str, conversation_id: str):
    """conversationId wins - Graph ties it to the whole thread even across a changed subject."""
    qs = InvitationEvent.objects.select_related("person", "event")
    if conversation_id:
        match = qs.filter(conversation_id=conversation_id).order_by("-created_at").first()
        if match:
            return match.person, match.event
    if tracking_code:
        match = qs.filter(tracking_code=tracking_code).order_by("-created_at").first()
        if match:
            return match.person, match.event
    return None, None


def record_email_reply(
    *, body: str, received_at, tracking_code: str = "", conversation_id: str = ""
) -> EmailReply:
    person, event = _resolve_person_and_event(tracking_code, conversation_id)
    classification = classify_reply(body)

    reply = EmailReply.objects.create(
        event=event,
        person=person,
        tracking_code=tracking_code,
        conversation_id=conversation_id,
        raw_body=body,
        received_at=received_at,
        classification=classification,
    )

    # Ambiguous, or we couldn't match a person/event: needs a human, no
    # auto-reply either - an unclear reply from a VIP deserves a real one.
    if classification == EmailClassification.AMBIGUOUS or person is None or event is None:
        return reply

    invitation = InvitationEvent.objects.create(
        person=person,
        event=event,
        event_type=(
            InvitationEventType.ACCEPTED
            if classification == EmailClassification.ACCEPTED
            else InvitationEventType.DECLINED
        ),
        channel=InvitationChannel.EMAIL,
        source_note=body[:500],
        tracking_code=tracking_code,
        conversation_id=conversation_id,
    )
    reply.resulting_invitation_event = invitation
    reply.save(update_fields=["resulting_invitation_event"])
    return reply


def resolve_ambiguous_reply(reply: EmailReply, decision: str, resolved_by: str) -> InvitationEvent:
    """Manual resolution of a reply the keyword classifier couldn't call on its own."""
    if reply.person_id is None or reply.event_id is None:
        raise ValueError("This reply never matched a person and event - link it manually first.")

    invitation = InvitationEvent.objects.create(
        person=reply.person,
        event=reply.event,
        event_type=(
            InvitationEventType.ACCEPTED if decision == "accepted" else InvitationEventType.DECLINED
        ),
        channel=InvitationChannel.EMAIL,
        source_note=reply.raw_body[:500],
        tracking_code=reply.tracking_code,
        conversation_id=reply.conversation_id,
    )
    reply.resulting_invitation_event = invitation
    reply.resolved_by = resolved_by
    reply.resolved_at = timezone.now()
    reply.save(update_fields=["resulting_invitation_event", "resolved_by", "resolved_at"])
    return invitation
