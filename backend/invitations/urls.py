from django.urls import path
from rest_framework.routers import DefaultRouter

from invitations.views import (
    CapacityView,
    EmailReplyViewSet,
    InvitationEventViewSet,
    PromotionSuggestionsView,
    StandbyContactViewSet,
)

router = DefaultRouter()
router.register("invitation-events", InvitationEventViewSet, basename="invitationevent")
router.register("email-replies", EmailReplyViewSet, basename="emailreply")
router.register("standby-contacts", StandbyContactViewSet, basename="standbycontact")

urlpatterns = router.urls + [
    path("capacity/", CapacityView.as_view(), name="capacity"),
    path("promotion-suggestions/", PromotionSuggestionsView.as_view(), name="promotion-suggestions"),
]
