from django.contrib import admin

from schedule.models import Announcement, PersonalAgendaItem, Room, Session


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "update_token")
    list_filter = ("event",)
    search_fields = ("name",)
    readonly_fields = ("update_token",)


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "room",
        "scheduled_start",
        "current_estimated_start",
        "status",
        "last_confirmed_at",
    )
    list_filter = ("status", "room__event", "room")
    search_fields = ("title", "speaker")
    autocomplete_fields = ("event", "room")


@admin.register(PersonalAgendaItem)
class PersonalAgendaItemAdmin(admin.ModelAdmin):
    list_display = ("person", "session", "added_at")
    autocomplete_fields = ("person", "session")


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ("message", "event", "audience_sector_tag", "created_by", "created_at")
    list_filter = ("event",)
    readonly_fields = ("created_at",)
