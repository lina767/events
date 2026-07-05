from rest_framework import serializers

from events.models import Event


class EventSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = [
            "id",
            "name",
            "category",
            "event_date",
            "target_capacity",
            "historical_show_rate",
            "created_at",
            "updated_at",
        ]
