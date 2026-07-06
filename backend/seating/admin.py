from django.contrib import admin

from seating.models import RelationshipEdge, SeatingWeights, SeatPin, Table, TableAssignment
from seating.services.assignments import confirm_event_seating


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "capacity")
    list_filter = ("event",)
    search_fields = ("name",)


@admin.register(RelationshipEdge)
class RelationshipEdgeAdmin(admin.ModelAdmin):
    list_display = ("person_a", "person_b", "edge_type", "is_hard_constraint")
    list_filter = ("edge_type", "is_hard_constraint")
    autocomplete_fields = ("person_a", "person_b")


@admin.register(SeatPin)
class SeatPinAdmin(admin.ModelAdmin):
    list_display = ("person", "table", "event")
    list_filter = ("event",)
    autocomplete_fields = ("person", "table")


@admin.register(SeatingWeights)
class SeatingWeightsAdmin(admin.ModelAdmin):
    list_display = ("event", "sector_diversity", "seniority_balance", "relationship_bonus")


@admin.register(TableAssignment)
class TableAssignmentAdmin(admin.ModelAdmin):
    list_display = ("person", "table", "event", "is_confirmed", "rationale")
    list_filter = ("event", "is_confirmed", "table")
    autocomplete_fields = ("person", "table")
    readonly_fields = ("rationale", "updated_at")
    actions = ["confirm_selected"]

    @admin.action(description="Confirm seating (ready to communicate to guests)")
    def confirm_selected(self, request, queryset):
        confirmed_by = request.user.get_username()
        count = 0
        for event_id in queryset.values_list("event_id", flat=True).distinct():
            count += confirm_event_seating(event_id, confirmed_by)
        self.message_user(request, f"{count} assignment(s) confirmed.")
