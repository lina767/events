from rest_framework import serializers

from invitations.models import EmailReply, InvitationEvent, StandbyContact


class InvitationEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvitationEvent
        fields = [
            "id",
            "person",
            "event",
            "event_type",
            "channel",
            "source_note",
            "tracking_code",
            "conversation_id",
            "created_at",
        ]
        read_only_fields = ["created_at"]


class EmailReplySerializer(serializers.ModelSerializer):
    needs_review = serializers.BooleanField(read_only=True)

    class Meta:
        model = EmailReply
        fields = [
            "id",
            "event",
            "person",
            "tracking_code",
            "conversation_id",
            "raw_body",
            "received_at",
            "classification",
            "resulting_invitation_event",
            "needs_review",
            "resolved_by",
            "resolved_at",
            "created_at",
        ]
        read_only_fields = fields


class RecordEmailReplySerializer(serializers.Serializer):
    body = serializers.CharField()
    received_at = serializers.DateTimeField()
    tracking_code = serializers.CharField(required=False, allow_blank=True, default="")
    conversation_id = serializers.CharField(required=False, allow_blank=True, default="")


class ResolveReplySerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["accepted", "declined"])
    resolved_by = serializers.CharField(max_length=255)


class BulkImportRowSerializer(serializers.Serializer):
    name = serializers.CharField()
    email = serializers.EmailField()


class BulkImportSerializer(serializers.Serializer):
    event = serializers.IntegerField()
    rows = BulkImportRowSerializer(many=True)


class PromoteSerializer(serializers.Serializer):
    nomination_id = serializers.IntegerField()
    decided_by = serializers.CharField(max_length=255)


class CapacitySerializer(serializers.Serializer):
    event = serializers.IntegerField()
    target_capacity = serializers.IntegerField()
    accepted_count = serializers.IntegerField()
    expected_attendance = serializers.DecimalField(max_digits=8, decimal_places=2)
    buffer = serializers.DecimalField(max_digits=8, decimal_places=2)
    needs_promotion = serializers.BooleanField()


class StandbyContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = StandbyContact
        fields = ["id", "event", "name", "phone", "notes", "order", "created_at"]
