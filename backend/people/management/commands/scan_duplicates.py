from django.core.management.base import BaseCommand

from people.services.matching import scan_all_for_duplicates


class Command(BaseCommand):
    help = (
        "Batch-cleanup mode for legacy data: pairwise-compares all active "
        "Persons and creates/refreshes pending DuplicateCandidate rows for "
        "review in bulk (Admin > Duplicate candidates), instead of "
        "reviewing one record at a time."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--threshold",
            type=int,
            default=None,
            help="Override GOLDEN_RECORD_DUPLICATE_THRESHOLD for this scan.",
        )

    def handle(self, *args, **options):
        count = scan_all_for_duplicates(threshold=options["threshold"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Scan abgeschlossen: {count} Duplikat-Kandidat(en) erstellt/aktualisiert."
            )
        )
