from people.tests.factories import make_person

from invitations.models import InvitationChannel, InvitationEvent, InvitationEventType


def make_invitation_event(person=None, event=None, event_type=InvitationEventType.INVITED, **kwargs) -> InvitationEvent:
    return InvitationEvent.objects.create(
        person=person or make_person(),
        event=event,
        event_type=event_type,
        channel=kwargs.pop("channel", InvitationChannel.MANUAL),
        **kwargs,
    )
