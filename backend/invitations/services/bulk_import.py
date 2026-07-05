"""
Bulk invite upload, keeping the familiar Excel/CSV workflow but replacing
its old exact-email dedup with real Golden Record matching: a brand-new
row creates a brand-new Person through the normal creation path, which
means Module 1's fuzzy-match signal - not just an exact-email check -
flags it as a possible duplicate for human review.
"""

from django.db import transaction

from people.models import Person, PersonEmail

from invitations.models import InvitationChannel, InvitationEvent, InvitationEventType


@transaction.atomic
def bulk_invite_from_rows(event, rows: list[dict]) -> list[InvitationEvent]:
    """rows: [{"name": str, "email": str}, ...] as parsed from the uploaded spreadsheet."""
    created_events = []
    seen_person_ids = set()

    for row in rows:
        email = row["email"].strip().lower()
        name = row["name"].strip()

        existing = PersonEmail.objects.filter(email__iexact=email).select_related("person").first()
        if existing:
            person = existing.person
        else:
            person = Person.objects.create(display_name=name)
            PersonEmail.objects.create(person=person, email=email, is_primary=True)

        if person.person_id in seen_person_ids:
            continue  # the same person appeared twice in this spreadsheet
        seen_person_ids.add(person.person_id)

        created_events.append(
            InvitationEvent.objects.create(
                person=person,
                event=event,
                event_type=InvitationEventType.INVITED,
                channel=InvitationChannel.EXCEL_IMPORT,
            )
        )

    return created_events
