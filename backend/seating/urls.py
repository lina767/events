from rest_framework.routers import DefaultRouter

from seating.views import (
    RelationshipEdgeViewSet,
    SeatingWeightsViewSet,
    SeatPinViewSet,
    TableAssignmentViewSet,
    TableViewSet,
)

router = DefaultRouter()
router.register("seating/tables", TableViewSet, basename="table")
router.register("seating/relationship-edges", RelationshipEdgeViewSet, basename="relationshipedge")
router.register("seating/seat-pins", SeatPinViewSet, basename="seatpin")
router.register("seating/weights", SeatingWeightsViewSet, basename="seatingweights")
router.register("seating/assignments", TableAssignmentViewSet, basename="tableassignment")

urlpatterns = router.urls
