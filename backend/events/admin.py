from django.contrib import admin

from events.models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "event_date", "target_capacity", "historical_show_rate")
    list_filter = ("category",)
    search_fields = ("name",)
