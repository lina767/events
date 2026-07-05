from django.contrib import admin

from invitations.models import EmailReply, InvitationEvent, StandbyContact
from invitations.services.email_parsing import resolve_ambiguous_reply


@admin.register(InvitationEvent)
class InvitationEventAdmin(admin.ModelAdmin):
    list_display = ("person", "event", "event_type", "channel", "created_at")
    list_filter = ("event_type", "channel", "event")
    search_fields = ("person__display_name", "tracking_code", "conversation_id")
    autocomplete_fields = ("person", "event")
    readonly_fields = ("created_at",)


@admin.register(EmailReply)
class EmailReplyAdmin(admin.ModelAdmin):
    list_display = ("person", "event", "classification", "needs_review", "received_at")
    list_filter = ("classification",)
    readonly_fields = ("raw_body", "classification", "received_at", "resulting_invitation_event")
    actions = ["resolve_as_accepted", "resolve_as_declined"]

    def _resolve(self, request, queryset, decision, verb):
        resolved_by = request.user.get_username()
        resolved = 0
        for reply in queryset.filter(resulting_invitation_event__isnull=True):
            if reply.person_id is None or reply.event_id is None:
                continue
            resolve_ambiguous_reply(reply, decision, resolved_by)
            resolved += 1
        self.message_user(request, f"{resolved} repl(ies) resolved as {verb}.")

    @admin.action(description="Resolve as accepted")
    def resolve_as_accepted(self, request, queryset):
        self._resolve(request, queryset, "accepted", "accepted")

    @admin.action(description="Resolve as declined")
    def resolve_as_declined(self, request, queryset):
        self._resolve(request, queryset, "declined", "declined")


@admin.register(StandbyContact)
class StandbyContactAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "phone", "order")
    list_filter = ("event",)
    ordering = ("event", "order")
