from rest_framework.routers import DefaultRouter

from nominations.views import NominationViewSet

router = DefaultRouter()
router.register("nominations", NominationViewSet, basename="nomination")

urlpatterns = router.urls
