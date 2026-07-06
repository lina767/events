from rest_framework.routers import DefaultRouter

from people.views import (
    DuplicateCandidateViewSet,
    PersonDeletionLogViewSet,
    PersonMergeLogViewSet,
    PersonViewSet,
)

router = DefaultRouter()
router.register("people", PersonViewSet, basename="person")
router.register("duplicate-candidates", DuplicateCandidateViewSet, basename="duplicatecandidate")
router.register("merge-logs", PersonMergeLogViewSet, basename="personmergelog")
router.register("deletion-logs", PersonDeletionLogViewSet, basename="persondeletionlog")

urlpatterns = router.urls
