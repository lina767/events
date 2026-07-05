from django.contrib import admin

from nominations.models import Nomination, NominationStatus
from nominations.services.decisions import approve, reject, waitlist


@admin.register(Nomination)
class NominationAdmin(admin.ModelAdmin):
    list_display = (
        "nominee_display_name",
        "event",
        "nominator",
        "status",
        "priority",
        "created_at",
    )
    list_filter = ("status", "event")
    search_fields = ("nominee_name", "nominee__display_name", "rationale")
    autocomplete_fields = ("event", "nominator", "nominee")
    actions = ["approve_selected", "reject_selected", "waitlist_selected"]

    def _decide(self, request, queryset, group_of, verb):
        performed_by = request.user.get_username()
        decided = set()
        for nomination in queryset.filter(status=NominationStatus.OPEN):
            if nomination.pk in decided:
                continue
            decided.update(n.pk for n in group_of(nomination, performed_by))
        self.message_user(request, f"{len(decided)} nomination(s) {verb}.")

    @admin.action(description="Approve (and every open duplicate proposal for the same nominee)")
    def approve_selected(self, request, queryset):
        self._decide(request, queryset, lambda n, by: approve(n, by)[1], "approved")

    @admin.action(description="Reject (and every open duplicate proposal for the same nominee)")
    def reject_selected(self, request, queryset):
        self._decide(request, queryset, reject, "rejected")

    @admin.action(description="Move to waitlist")
    def waitlist_selected(self, request, queryset):
        self._decide(request, queryset, waitlist, "waitlisted")
