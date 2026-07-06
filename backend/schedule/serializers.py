from people.serializers import PersonSerializer
from rest_framework import serializers

from schedule.models import Announcement, PersonalAgendaItem, Room, Session
from schedule.services.traffic_light import traffic_light


class SessionSerializer(serializers.ModelSerializer):
    traffic_light = serializers.SerializerMethodField()

    class Meta:
        model = Session
        fields = [
            "id",
            "event",
            "room",
            "title",
            "speaker",
            "scheduled_start",
            "current_estimated_start",
            "status",
            "last_confirmed_at",
            "last_confirmed_by",
            "traffic_light",
        ]
        read_only_fields = [
            "current_estimated_start",
            "status",
            "last_confirmed_at",
            "last_confirmed_by",
        ]

    def get_traffic_light(self, session):
        light = traffic_light(session)
        return {"color": light.color, "label": light.label}


class RoomStatusSerializer(serializers.Serializer):
    """What the no-login room-update page shows: just current + next session."""

    room = serializers.CharField(source="name")
    current_session = SessionSerializer(allow_null=True)
    next_session = SessionSerializer(allow_null=True)


class RoomUpdateActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(
        choices=["confirm", "delay_10", "delay_30", "running", "cancelled"]
    )
    confirmed_by = serializers.CharField(max_length=255)


class ApplyShiftSerializer(serializers.Serializer):
    session_ids = serializers.ListField(child=serializers.IntegerField())
    minutes = serializers.IntegerField()
    confirmed_by = serializers.CharField(max_length=255)


class AgendaItemSerializer(serializers.ModelSerializer):
    session = SessionSerializer(read_only=True)

    class Meta:
        model = PersonalAgendaItem
        fields = ["id", "person", "session", "added_at"]


class AddAgendaItemSerializer(serializers.Serializer):
    person = serializers.UUIDField()
    session = serializers.IntegerField()


class AnnouncementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ["id", "event", "message", "audience_sector_tag", "created_by", "created_at"]
        read_only_fields = ["created_at"]
