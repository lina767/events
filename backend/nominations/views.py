from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from nominations.models import Nomination
from nominations.serializers import (
    BatchDecideSerializer,
    DecideSerializer,
    NominationCreateSerializer,
    NominationGroupSerializer,
    NominationSerializer,
)
from nominations.services.bundling import group_pending
from nominations.services.decisions import approve, batch_decide, reject, waitlist


class NominationViewSet(viewsets.ModelViewSet):
    queryset = Nomination.objects.select_related("event", "nominator", "nominee")
    serializer_class = NominationSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return NominationCreateSerializer
        return super().get_serializer_class()

    def get_queryset(self):
        qs = super().get_queryset()
        event_id = self.request.query_params.get("event")
        if event_id:
            qs = qs.filter(event_id=event_id)
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    @action(detail=False, methods=["get"], url_path="grouped-pending")
    def grouped_pending(self, request):
        """Open nominations for one event, bundled by nominee for one-shot review."""
        event_id = request.query_params.get("event")
        groups = group_pending(event_id) if event_id else []
        data = [
            {"nominee_display_name": group[0].nominee_display_name, "nominations": group}
            for group in groups
        ]
        return Response(NominationGroupSerializer(data, many=True).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        serializer = DecideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nomination = self.get_object()
        _, group = approve(nomination, serializer.validated_data["decided_by"])
        return Response(NominationSerializer(group, many=True).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        serializer = DecideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nomination = self.get_object()
        group = reject(nomination, serializer.validated_data["decided_by"])
        return Response(NominationSerializer(group, many=True).data)

    @action(detail=True, methods=["post"])
    def waitlist(self, request, pk=None):
        serializer = DecideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nomination = self.get_object()
        group = waitlist(nomination, serializer.validated_data["decided_by"])
        return Response(NominationSerializer(group, many=True).data)

    @action(detail=False, methods=["post"], url_path="batch-decide")
    def batch_decide_view(self, request):
        """The "batch round" mode: decide a whole slate of nominations at once."""
        serializer = BatchDecideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        decided_ids = batch_decide(
            serializer.validated_data["decisions"], serializer.validated_data["decided_by"]
        )
        return Response({"decided_ids": decided_ids})
