from django.shortcuts import get_object_or_404
from events.models import Event
from people.models import Person
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from seating.models import RelationshipEdge, SeatingWeights, SeatPin, Table, TableAssignment
from seating.serializers import (
    ConfirmSeatingSerializer,
    PinSeatSerializer,
    RelationshipEdgeSerializer,
    RunLocalReoptimizationSerializer,
    RunOptimizationSerializer,
    SeatingWeightsSerializer,
    SeatPinSerializer,
    TableAssignmentSerializer,
    TableSerializer,
)
from seating.services.assignments import (
    confirm_event_seating,
    run_full_optimization,
    run_local_reoptimization,
)
from seating.services.pins import pin_seat, unpin_seat


class TableViewSet(viewsets.ModelViewSet):
    queryset = Table.objects.select_related("event")
    serializer_class = TableSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        event_id = self.request.query_params.get("event")
        if event_id:
            qs = qs.filter(event_id=event_id)
        return qs


class RelationshipEdgeViewSet(viewsets.ModelViewSet):
    queryset = RelationshipEdge.objects.select_related("person_a", "person_b")
    serializer_class = RelationshipEdgeSerializer


class SeatPinViewSet(viewsets.ModelViewSet):
    queryset = SeatPin.objects.select_related("person", "table")
    serializer_class = SeatPinSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        event_id = self.request.query_params.get("event")
        if event_id:
            qs = qs.filter(event_id=event_id)
        return qs


class SeatingWeightsViewSet(viewsets.ModelViewSet):
    queryset = SeatingWeights.objects.all()
    serializer_class = SeatingWeightsSerializer


class TableAssignmentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TableAssignment.objects.select_related("person", "table")
    serializer_class = TableAssignmentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        event_id = self.request.query_params.get("event")
        if event_id:
            qs = qs.filter(event_id=event_id)
        return qs

    @action(detail=False, methods=["post"], url_path="optimize")
    def optimize(self, request):
        """Full re-run over every table - the initial plan, or a deliberate reshuffle."""
        serializer = RunOptimizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = get_object_or_404(Event, pk=request.data.get("event"))
        assignments = run_full_optimization(event, **serializer.validated_data)
        return Response(TableAssignmentSerializer(assignments, many=True).data)

    @action(detail=False, methods=["post"], url_path="reoptimize-local")
    def reoptimize_local(self, request):
        """Reoptimize only the table(s) touched by a change, not the whole room."""
        serializer = RunLocalReoptimizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = get_object_or_404(Event, pk=request.data.get("event"))
        assignments = run_local_reoptimization(event, **serializer.validated_data)
        return Response(TableAssignmentSerializer(assignments, many=True).data)

    @action(detail=False, methods=["post"], url_path="confirm")
    def confirm(self, request):
        """The explicit human sign-off - nothing is communicated to guests before this."""
        serializer = ConfirmSeatingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = get_object_or_404(Event, pk=request.data.get("event"))
        count = confirm_event_seating(event, serializer.validated_data["confirmed_by"])
        return Response({"confirmed_count": count})

    @action(detail=False, methods=["post"], url_path="pin")
    def pin(self, request):
        serializer = PinSeatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = get_object_or_404(Event, pk=request.data.get("event"))
        person = get_object_or_404(Person, pk=serializer.validated_data["person"])
        table = get_object_or_404(Table, pk=serializer.validated_data["table"])
        pin_seat(event, person, table)
        return Response(TableAssignmentSerializer(TableAssignment.objects.get(event=event, person=person)).data)

    @action(detail=False, methods=["post"], url_path="unpin")
    def unpin(self, request):
        event = get_object_or_404(Event, pk=request.data.get("event"))
        person = get_object_or_404(Person, pk=request.data.get("person"))
        unpin_seat(event, person)
        return Response(status=204)
