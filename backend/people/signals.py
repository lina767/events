from django.db.models.signals import post_save
from django.dispatch import receiver

from people.models import Person, PersonEmail
from people.services.matching import find_duplicate_candidates


@receiver(post_save, sender=Person)
def check_for_duplicates_on_create(sender, instance: Person, created, **kwargs):
    """
    Every new Person (import, manual entry, email-reply parsing) is
    fuzzy-matched against existing active Persons. Never auto-merges -
    only ever creates DuplicateCandidate rows for human review.
    """
    if created and instance.is_active:
        find_duplicate_candidates(instance)


@receiver(post_save, sender=PersonEmail)
def recheck_duplicates_on_email_added(sender, instance: PersonEmail, created, **kwargs):
    """
    Adding an email can surface a shared-domain signal that wasn't visible
    when the Person record itself was first created.
    """
    if created and instance.person.is_active:
        find_duplicate_candidates(instance.person)
