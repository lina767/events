from django.shortcuts import get_object_or_404
from people.models import Person
from people.serializers import PersonSerializer
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from schedule.models import Announcement, Room, Session
from schedule.serializers import (
    AddAgendaItemSerializer,
    AgendaItemSerializer,
    AnnouncementSerializer,
    ApplyShiftSerializer,
    RoomStatusSerializer,
    RoomUpdateActionSerializer,
    SessionSerializer,
)
from schedule.services.agenda import add_to_agenda, get_agenda, remove_from_agenda
from schedule.services.announcements import create_announcement, list_announcements
from schedule.services.networking import search_attendees
from schedule.services.updates import (
    apply_shift_to_sessions,
    cancel,
    confirm_on_time,
    current_and_next_session,
    delay,
    mark_running,
    subsequent_sessions_in_room,
)

_ACTIONS = {
    "confirm": lambda session, by: confirm_on_time(session, by),
    "delay_10": lambda session, by: delay(session, 10, by),
    "delay_30": lambda session, by: delay(session, 30, by),
    "running": lambda session, by: mark_running(session, by),
    "cancelled": lambda session, by: cancel(session, by),
}


class SessionViewSet(viewsets.ModelViewSet):
    """The participant-facing schedule - meant to be polled every 15-30s, not pushed to."""

    queryset = Session.objects.select_related("room", "event")
    serializer_class = SessionSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        event_id = self.request.query_params.get("event")
        if event_id:
            qs = qs.filter(event_id=event_id)
        room_id = self.request.query_params.get("room")
        if room_id:
            qs = qs.filter(room_id=room_id)
        return qs


class RoomStatusView(APIView):
    """GET /api/schedule/rooms/<token>/status/ - no login, just the unguessable token."""

    def get(self, request, token):
        room = get_object_or_404(Room, update_token=token)
        current, next_session = current_and_next_session(room)
        data = {"name": room.name, "current_session": current, "next_session": next_session}
        return Response(RoomStatusSerializer(data).data)


class RoomUpdateView(APIView):
    """
    POST /api/schedule/rooms/<token>/update/ - the one-tap buttons: confirm,
    delay_10, delay_30, running, cancelled. Returns the updated session plus
    any subsequent sessions in the room a delay could cascade into, so the
    caller can offer (never force) shifting them too.
    """

    def post(self, request, token):
        room = get_object_or_404(Room, update_token=token)
        serializer = RoomUpdateActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        current, _ = current_and_next_session(room)
        if current is None:
            return Response({"detail": "No active session in this room right now."}, status=400)

        action_fn = _ACTIONS[serializer.validated_data["action"]]
        session = action_fn(current, serializer.validated_data["confirmed_by"])

        return Response(
            {
                "session": SessionSerializer(session).data,
                "suggested_shift_candidates": SessionSerializer(
                    subsequent_sessions_in_room(session), many=True
                ).data,
            }
        )


class RoomApplyShiftView(APIView):
    """POST /api/schedule/rooms/<token>/apply-shift/ - confirming the cascade suggestion."""

    def post(self, request, token):
        get_object_or_404(Room, update_token=token)
        serializer = ApplyShiftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sessions = list(Session.objects.filter(pk__in=serializer.validated_data["session_ids"]))
        updated = apply_shift_to_sessions(
            sessions, serializer.validated_data["minutes"], serializer.validated_data["confirmed_by"]
        )
        return Response(SessionSerializer(updated, many=True).data)


class AgendaView(APIView):
    """GET/POST /api/schedule/agenda/ - a participant's personal agenda."""

    def get(self, request):
        person = get_object_or_404(Person, pk=request.query_params.get("person"))
        event_id = request.query_params.get("event")
        sessions = get_agenda(person, event_id)
        return Response(SessionSerializer(sessions, many=True).data)

    def post(self, request):
        serializer = AddAgendaItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        person = get_object_or_404(Person, pk=serializer.validated_data["person"])
        session = get_object_or_404(Session, pk=serializer.validated_data["session"])
        item = add_to_agenda(person, session)
        return Response(AgendaItemSerializer(item).data)

    def delete(self, request):
        serializer = AddAgendaItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        person = get_object_or_404(Person, pk=serializer.validated_data["person"])
        session = get_object_or_404(Session, pk=serializer.validated_data["session"])
        remove_from_agenda(person, session)
        return Response(status=204)


class AttendeeSearchView(APIView):
    """GET /api/schedule/attendees/ - networking: search Golden Record data, scoped to this event."""

    def get(self, request):
        event_id = request.query_params.get("event")
        query = request.query_params.get("q", "")
        sector = request.query_params.get("sector", "")
        results = search_attendees(event_id, query=query, sector_tag=sector)
        return Response(PersonSerializer(results, many=True).data)


class AnnouncementViewSet(viewsets.ModelViewSet):
    """
    Standard CRUD for authoring. Participants poll GET .../feed/ instead,
    which applies the "everyone, plus my own track" audience rule.
    """

    queryset = Announcement.objects.all()
    serializer_class = AnnouncementSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        event_id = self.request.query_params.get("event")
        if event_id:
            qs = qs.filter(event_id=event_id)
        return qs

    @action(detail=False, methods=["get"])
    def feed(self, request):
        event_id = request.query_params.get("event")
        announcements = list_announcements(
            event_id,
            for_sector_tag=request.query_params.get("sector", ""),
            since=request.query_params.get("since"),
        )
        return Response(AnnouncementSerializer(announcements, many=True).data)
