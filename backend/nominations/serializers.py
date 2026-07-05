from rest_framework import serializers

from people.serializers import PersonSerializer

from nominations.models import Nomination


class NominationSerializer(serializers.ModelSerializer):
    nominee = PersonSerializer(read_only=True)
    nominee_display_name = serializers.CharField(read_only=True)

    class Meta:
        model = Nomination
        fields = [
            "id",
            "event",
            "nominator",
            "nominee",
            "nominee_name",
            "nominee_organization",
            "nominee_display_name",
            "rationale",
            "status",
            "priority",
            "created_at",
            "decided_at",
            "decided_by",
        ]
        read_only_fields = ["status", "decided_at", "decided_by"]


class NominationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Nomination
        fields = [
            "id",
            "event",
            "nominator",
            "nominee",
            "nominee_name",
            "nominee_organization",
            "rationale",
            "priority",
        ]

    def validate(self, data):
        if not data.get("nominee") and not data.get("nominee_name"):
            raise serializers.ValidationError(
                "A nomination needs either an existing nominee or a nominee_name."
            )
        return data


class NominationGroupSerializer(serializers.Serializer):
    nominee_display_name = serializers.CharField()
    nominations = NominationSerializer(many=True)


class DecideSerializer(serializers.Serializer):
    decided_by = serializers.CharField(max_length=255)


class BatchDecisionItemSerializer(serializers.Serializer):
    nomination_id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=["approve", "reject", "waitlist"])


class BatchDecideSerializer(serializers.Serializer):
    decided_by = serializers.CharField(max_length=255)
    decisions = BatchDecisionItemSerializer(many=True)
