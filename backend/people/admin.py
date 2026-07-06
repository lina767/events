from django.contrib import admin
from django.utils import timezone

from people.models import (
    DuplicateCandidate,
    DuplicateCandidateStatus,
    Person,
    PersonDeletionLog,
    PersonEmail,
    PersonMergeLog,
)
from people.services.deletion import erase_person
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
    list_filter = (
        "is_active",
        "is_deleted",
        "flagged_for_review",
        "consent_status",
        "seniority_level",
    )
    search_fields = ("display_name", "normalized_name", "organization")
    readonly_fields = ("person_id", "normalized_name", "is_deleted", "created_at", "updated_at")
    inlines = [PersonEmailInline]
    actions = ["mark_verified", "erase_selected"]

    @admin.action(description="Mark as recently verified")
    def mark_verified(self, request, queryset):
        updated = queryset.update(last_verified_at=timezone.now(), flagged_for_review=False)
        self.message_user(request, f"{updated} person(s) marked as verified.")

    @admin.action(description="Erase (execute a deletion request)")
    def erase_selected(self, request, queryset):
        performed_by = request.user.get_username()
        erased = 0
        for person in queryset.filter(is_deleted=False):
            erase_person(person, performed_by=performed_by)
            erased += 1
        self.message_user(
            request,
            f"{erased} person(s) erased. Add the request rationale in "
            f"Admin > People > Deletion log.",
        )


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
                rationale="Bulk confirmation via admin batch cleanup",
                confidence_score=candidate.confidence_score,
                duplicate_candidate=candidate,
            )
        self.message_user(request, f"{len(pending)} duplicate(s) merged.")

    @admin.action(description="Confirm: keep Person A, merge B into it")
    def confirm_keep_a(self, request, queryset):
        self._confirm(request, queryset, keep="a")

    @admin.action(description="Confirm: keep Person B, merge A into it")
    def confirm_keep_b(self, request, queryset):
        self._confirm(request, queryset, keep="b")

    @admin.action(description="Reject: not a duplicate")
    def reject(self, request, queryset):
        performed_by = request.user.get_username()
        pending = list(queryset.filter(status=DuplicateCandidateStatus.PENDING))
        for candidate in pending:
            reject_duplicate_candidate(candidate, performed_by)
        self.message_user(request, f"{len(pending)} candidate(s) marked as not a duplicate.")


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

    @admin.action(description="Revert merge")
    def revert(self, request, queryset):
        performed_by = request.user.get_username()
        reverted = list(queryset.filter(reverted_at__isnull=True))
        for log in reverted:
            revert_merge(log, performed_by)
        self.message_user(request, f"{len(reverted)} merge(s) reverted.")


@admin.register(PersonDeletionLog)
class PersonDeletionLogAdmin(admin.ModelAdmin):
    list_display = ("person", "requested_by", "performed_by", "performed_at")
    readonly_fields = ("person", "performed_by", "performed_at")

    def has_add_permission(self, request):
        return False
