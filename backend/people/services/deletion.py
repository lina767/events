"""
Executes a deletion/erasure request against the Golden Record. The
Person row survives as a tombstone (other modules' foreign keys to
person_id must keep resolving), but every field that carries personal
data is scrubbed and every email is removed outright.
"""

from django.db import transaction
from django.utils import timezone

from people.models import ConsentStatus, Person, PersonDeletionLog


class DeletionError(Exception):
    pass


@transaction.atomic
def erase_person(
    person: Person, performed_by: str, requested_by: str = "", reason: str = ""
) -> PersonDeletionLog:
    if person.is_deleted:
        raise DeletionError("This person has already been erased.")

    person.emails.all().delete()

    person.display_name = "Deleted person"
    person.organization = ""
    person.sector_tags = []
    person.seniority_level = ""
    person.consent_status = ConsentStatus.REVOKED
    person.data_retention_note = (
        f"Erased {timezone.now():%Y-%m-%d} following a deletion request."
    )
    person.is_active = False
    person.is_deleted = True
    person.flagged_for_review = False
    person.save()

    return PersonDeletionLog.objects.create(
        person=person, requested_by=requested_by, performed_by=performed_by, reason=reason
    )
