from rest_framework import serializers

from people.models import DuplicateCandidate, Person, PersonEmail, PersonMergeLog


class PersonEmailSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonEmail
        fields = ["id", "email", "is_primary", "created_at"]


class PersonSerializer(serializers.ModelSerializer):
    emails = PersonEmailSerializer(many=True, read_only=True)

    class Meta:
        model = Person
        fields = [
            "person_id",
            "display_name",
            "organization",
            "sector_tags",
            "seniority_level",
            "last_verified_at",
            "consent_status",
            "data_retention_note",
            "is_active",
            "merged_into",
            "flagged_for_review",
            "emails",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["is_active", "merged_into", "flagged_for_review"]


class PersonCreateSerializer(serializers.ModelSerializer):
    """Accepts an initial list of emails on creation of a new Person."""

    emails = serializers.ListField(
        child=serializers.EmailField(), required=False, write_only=True, default=list
    )

    class Meta:
        model = Person
        fields = [
            "person_id",
            "display_name",
            "organization",
            "sector_tags",
            "seniority_level",
            "last_verified_at",
            "consent_status",
            "data_retention_note",
            "emails",
        ]
        read_only_fields = ["person_id"]

    def create(self, validated_data):
        emails = validated_data.pop("emails", [])
        person = Person.objects.create(**validated_data)
        for index, email in enumerate(emails):
            PersonEmail.objects.create(person=person, email=email, is_primary=index == 0)
        return person


class DuplicateCandidateSerializer(serializers.ModelSerializer):
    person_a = PersonSerializer(read_only=True)
    person_b = PersonSerializer(read_only=True)

    class Meta:
        model = DuplicateCandidate
        fields = [
            "id",
            "person_a",
            "person_b",
            "confidence_score",
            "reasons",
            "status",
            "detected_at",
            "decided_at",
            "decided_by",
        ]
        read_only_fields = fields


class ConfirmDuplicateSerializer(serializers.Serializer):
    keep = serializers.ChoiceField(choices=["a", "b"])
    performed_by = serializers.CharField(max_length=255)
    rationale = serializers.CharField(required=False, allow_blank=True, default="")


class RejectDuplicateSerializer(serializers.Serializer):
    performed_by = serializers.CharField(max_length=255)


class PersonMergeLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PersonMergeLog
        fields = [
            "id",
            "source_person",
            "target_person",
            "duplicate_candidate",
            "confidence_score",
            "rationale",
            "performed_by",
            "performed_at",
            "reverted_at",
            "reverted_by",
        ]
        read_only_fields = fields
