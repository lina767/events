from people.serializers import PersonSerializer
from rest_framework import serializers

from seating.models import RelationshipEdge, SeatingWeights, SeatPin, Table, TableAssignment


class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = ["id", "event", "name", "capacity"]


class RelationshipEdgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RelationshipEdge
        fields = ["id", "person_a", "person_b", "edge_type", "is_hard_constraint"]


class SeatPinSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeatPin
        fields = ["id", "event", "person", "table"]


class SeatingWeightsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeatingWeights
        fields = ["id", "event", "sector_diversity", "seniority_balance", "relationship_bonus"]


class TableAssignmentSerializer(serializers.ModelSerializer):
    person = PersonSerializer(read_only=True)

    class Meta:
        model = TableAssignment
        fields = [
            "id",
            "event",
            "person",
            "table",
            "rationale",
            "is_confirmed",
            "confirmed_by",
            "confirmed_at",
            "updated_at",
        ]
        read_only_fields = ["rationale", "is_confirmed", "confirmed_by", "confirmed_at"]


class RunOptimizationSerializer(serializers.Serializer):
    iterations = serializers.IntegerField(required=False, default=1500)
    seed = serializers.IntegerField(required=False, allow_null=True, default=None)


class RunLocalReoptimizationSerializer(serializers.Serializer):
    changed_person_ids = serializers.ListField(child=serializers.UUIDField())
    iterations = serializers.IntegerField(required=False, default=500)
    seed = serializers.IntegerField(required=False, allow_null=True, default=None)


class ConfirmSeatingSerializer(serializers.Serializer):
    confirmed_by = serializers.CharField(max_length=255)


class PinSeatSerializer(serializers.Serializer):
    person = serializers.UUIDField()
    table = serializers.IntegerField()
