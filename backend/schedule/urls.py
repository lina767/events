from django.urls import path
from rest_framework.routers import DefaultRouter

from schedule.views import (
    AgendaView,
    AnnouncementViewSet,
    AttendeeSearchView,
    RoomApplyShiftView,
    RoomStatusView,
    RoomUpdateView,
    SessionViewSet,
)

router = DefaultRouter()
router.register("schedule/sessions", SessionViewSet, basename="session")
router.register("schedule/announcements", AnnouncementViewSet, basename="announcement")

urlpatterns = router.urls + [
    path("schedule/rooms/<uuid:token>/status/", RoomStatusView.as_view(), name="room-status"),
    path("schedule/rooms/<uuid:token>/update/", RoomUpdateView.as_view(), name="room-update"),
    path(
        "schedule/rooms/<uuid:token>/apply-shift/",
        RoomApplyShiftView.as_view(),
        name="room-apply-shift",
    ),
    path("schedule/agenda/", AgendaView.as_view(), name="agenda"),
    path("schedule/attendees/", AttendeeSearchView.as_view(), name="attendee-search"),
]
