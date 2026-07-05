from django.shortcuts import get_object_or_404
from events.models import Event
from nominations.models import Nomination
from nominations.serializers import NominationSerializer
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from invitations.models import EmailReply, InvitationEvent, StandbyContact
from invitations.serializers import (
    BulkImportSerializer,
    CapacitySerializer,
    EmailReplySerializer,
    InvitationEventSerializer,
    PromoteSerializer,
    RecordEmailReplySerializer,
    ResolveReplySerializer,
    StandbyContactSerializer,
)
from invitations.services.bulk_import import bulk_invite_from_rows
from invitations.services.capacity import accepted_count, buffer, expected_attendance, needs_promotion
from invitations.services.email_parsing import record_email_reply, resolve_ambiguous_reply
from invitations.services.promotion import promote_from_waitlist, suggest_promotions


class InvitationEventViewSet(viewsets.ModelViewSet):
    queryset = InvitationEvent.objects.select_related("person", "event")
    serializer_class = InvitationEventSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        event_id = self.request.query_params.get("event")
        if event_id:
            qs = qs.filter(event_id=event_id)
        person_id = self.request.query_params.get("person")
        if person_id:
            qs = qs.filter(person_id=person_id)
        return qs

    @action(detail=False, methods=["post"], url_path="record-email-reply")
    def record_email_reply_view(self, request):
        serializer = RecordEmailReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reply = record_email_reply(**serializer.validated_data)
        return Response(EmailReplySerializer(reply).data)

    @action(detail=False, methods=["post"], url_path="bulk-import")
    def bulk_import(self, request):
        serializer = BulkImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = get_object_or_404(Event, pk=serializer.validated_data["event"])
        created = bulk_invite_from_rows(event, serializer.validated_data["rows"])
        return Response(InvitationEventSerializer(created, many=True).data)

    @action(detail=False, methods=["post"], url_path="promote-from-waitlist")
    def promote(self, request):
        serializer = PromoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nomination = get_object_or_404(Nomination, pk=serializer.validated_data["nomination_id"])
        invitation = promote_from_waitlist(nomination, serializer.validated_data["decided_by"])
        return Response(InvitationEventSerializer(invitation).data)


class CapacityView(APIView):
    """GET /api/capacity/?event=<id> - the overbooking math behind the promotion decision."""

    def get(self, request):
        event = get_object_or_404(Event, pk=request.query_params.get("event"))
        data = {
            "event": event.pk,
            "target_capacity": event.target_capacity,
            "accepted_count": accepted_count(event),
            "expected_attendance": expected_attendance(event),
            "buffer": buffer(event),
            "needs_promotion": needs_promotion(event),
        }
        return Response(CapacitySerializer(data).data)


class PromotionSuggestionsView(APIView):
    """GET /api/promotion-suggestions/?event=<id> - shows candidates, decides nothing."""

    def get(self, request):
        event = get_object_or_404(Event, pk=request.query_params.get("event"))
        suggestions = suggest_promotions(event)
        return Response(NominationSerializer(suggestions, many=True).data)


class EmailReplyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EmailReply.objects.select_related("person", "event")
    serializer_class = EmailReplySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("needs_review") == "true":
            qs = qs.filter(resulting_invitation_event__isnull=True)
        return qs

    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        serializer = ResolveReplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reply = self.get_object()
        invitation = resolve_ambiguous_reply(reply, **serializer.validated_data)
        return Response(InvitationEventSerializer(invitation).data)


class StandbyContactViewSet(viewsets.ModelViewSet):
    queryset = StandbyContact.objects.select_related("event")
    serializer_class = StandbyContactSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        event_id = self.request.query_params.get("event")
        if event_id:
            qs = qs.filter(event_id=event_id)
        return qs
