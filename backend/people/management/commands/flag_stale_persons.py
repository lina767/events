from django.conf import settings
from django.core.management.base import BaseCommand

from people.models import Person


class Command(BaseCommand):
    help = (
        "Marks active Persons whose last_verified_at is older than "
        "GOLDEN_RECORD_STALE_MONTHS (or missing) as flagged_for_review. "
        "Does not delete or merge anything - just surfaces them for a "
        "periodic relevance check."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--months",
            type=int,
            default=None,
            help="Override GOLDEN_RECORD_STALE_MONTHS for this run.",
        )

    def handle(self, *args, **options):
        months = options["months"] or settings.GOLDEN_RECORD_STALE_MONTHS
        flagged = 0
        for person in Person.objects.filter(is_active=True, flagged_for_review=False):
            if person.is_stale(months):
                person.flagged_for_review = True
                person.save(update_fields=["flagged_for_review"])
                flagged += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"{flagged} Person(en) älter als {months} Monate zur Überprüfung markiert."
            )
        )
