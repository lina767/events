from django.contrib import admin
from django.urls import include, path

from eventflow import admin_site  # noqa: F401  (applies custom admin ordering)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("people.urls")),
    path("api/", include("events.urls")),
    path("api/", include("nominations.urls")),
    path("api/", include("invitations.urls")),
    path("api/", include("schedule.urls")),
    path("api/", include("seating.urls")),
]
