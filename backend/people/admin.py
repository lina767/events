from django.contrib import admin
from django.utils import timezone

from people.models import (
    DuplicateCandidate,
    DuplicateCandidateStatus,
    Person,
    PersonEmail,
    PersonMergeLog,
)
from people.services.merging import merge_persons, reject_duplicate_candidate, revert_merge


class PersonEmailInline(admin.TabularInline):
    model = PersonEmail
    extra = 0


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = (
        "display_name",
        "organization",
        "seniority_level",
        "consent_status",
        "is_active",
        "flagged_for_review",
        "last_verified_at",
    )
    list_filter = ("is_active", "flagged_for_review", "consent_status", "seniority_level")
    search_fields = ("display_name", "normalized_name", "organization")
    readonly_fields = ("person_id", "normalized_name", "created_at", "updated_at")
    inlines = [PersonEmailInline]
    actions = ["mark_verified"]

    @admin.action(description="Als aktuell überprüft markieren")
    def mark_verified(self, request, queryset):
        updated = queryset.update(last_verified_at=timezone.now(), flagged_for_review=False)
        self.message_user(request, f"{updated} Person(en) als überprüft markiert.")


@admin.register(DuplicateCandidate)
class DuplicateCandidateAdmin(admin.ModelAdmin):
    """
    The bulk-review screen for batch cleanup: select a cluster of rows and
    confirm or reject in one action, instead of record by record.
    """

    list_display = ("person_a", "person_b", "confidence_score", "status", "detected_at")
    list_filter = ("status",)
    readonly_fields = ("person_a", "person_b", "confidence_score", "reasons", "detected_at")
    actions = ["confirm_keep_a", "confirm_keep_b", "reject"]

    def _confirm(self, request, queryset, keep):
        performed_by = request.user.get_username()
        pending = list(queryset.filter(status=DuplicateCandidateStatus.PENDING))
        for candidate in pending:
            source, target = (
                (candidate.person_b, candidate.person_a)
                if keep == "a"
                else (candidate.person_a, candidate.person_b)
            )
            merge_persons(
                source=source,
                target=target,
                performed_by=performed_by,
                rationale="Bulk-Bestätigung über Admin-Batch-Cleanup",
                confidence_score=candidate.confidence_score,
                duplicate_candidate=candidate,
            )
        self.message_user(request, f"{len(pending)} Duplikat(e) zusammengeführt.")

    @admin.action(description="Bestätigen: Person A behalten, B zusammenführen")
    def confirm_keep_a(self, request, queryset):
        self._confirm(request, queryset, keep="a")

    @admin.action(description="Bestätigen: Person B behalten, A zusammenführen")
    def confirm_keep_b(self, request, queryset):
        self._confirm(request, queryset, keep="b")

    @admin.action(description="Ablehnen: kein Duplikat")
    def reject(self, request, queryset):
        performed_by = request.user.get_username()
        pending = list(queryset.filter(status=DuplicateCandidateStatus.PENDING))
        for candidate in pending:
            reject_duplicate_candidate(candidate, performed_by)
        self.message_user(request, f"{len(pending)} Kandidat(en) als 'kein Duplikat' markiert.")


@admin.register(PersonMergeLog)
class PersonMergeLogAdmin(admin.ModelAdmin):
    list_display = (
        "source_person",
        "target_person",
        "performed_by",
        "performed_at",
        "reverted_at",
    )
    readonly_fields = [f.name for f in PersonMergeLog._meta.fields]
    actions = ["revert"]

    def has_add_permission(self, request):
        return False

    @admin.action(description="Zusammenführung rückgängig machen")
    def revert(self, request, queryset):
        performed_by = request.user.get_username()
        reverted = list(queryset.filter(reverted_at__isnull=True))
        for log in reverted:
            revert_merge(log, performed_by)
        self.message_user(request, f"{len(reverted)} Zusammenführung(en) rückgängig gemacht.")
