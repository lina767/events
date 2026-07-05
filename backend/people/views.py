from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from people.models import DuplicateCandidate, DuplicateCandidateStatus, Person, PersonMergeLog
from people.serializers import (
    ConfirmDuplicateSerializer,
    DuplicateCandidateSerializer,
    PersonCreateSerializer,
    PersonMergeLogSerializer,
    PersonSerializer,
    RejectDuplicateSerializer,
)
from people.services.merging import (
    MergeError,
    merge_persons,
    reject_duplicate_candidate,
    revert_merge,
)


class PersonViewSet(viewsets.ModelViewSet):
    queryset = Person.objects.all().prefetch_related("emails")
    serializer_class = PersonSerializer

    def get_serializer_class(self):
        if self.action == "create":
            return PersonCreateSerializer
        return PersonSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("active_only") == "true":
            qs = qs.filter(is_active=True)
        return qs

    @action(detail=False, methods=["get"], url_path="needs-review")
    def needs_review(self, request):
        """Persons flagged because last_verified_at is stale (see flag_stale_persons)."""
        qs = self.get_queryset().filter(is_active=True, flagged_for_review=True)
        page = self.paginate_queryset(qs)
        serializer = PersonSerializer(page or qs, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], url_path="verify")
    def verify(self, request, pk=None):
        """Mark a Person as freshly reviewed, clearing the stale flag."""
        person = self.get_object()
        person.last_verified_at = timezone.now()
        person.flagged_for_review = False
        person.save(update_fields=["last_verified_at", "flagged_for_review"])
        return Response(PersonSerializer(person).data)


class DuplicateCandidateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DuplicateCandidate.objects.select_related("person_a", "person_b")
    serializer_class = DuplicateCandidateSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        else:
            qs = qs.filter(status=DuplicateCandidateStatus.PENDING)
        return qs

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """Human confirms this pair is the same person - merge them."""
        candidate = self.get_object()
        serializer = ConfirmDuplicateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        source, target = (
            (candidate.person_b, candidate.person_a)
            if data["keep"] == "a"
            else (candidate.person_a, candidate.person_b)
        )

        try:
            merge_persons(
                source=source,
                target=target,
                performed_by=data["performed_by"],
                rationale=data["rationale"],
                confidence_score=candidate.confidence_score,
                duplicate_candidate=candidate,
            )
        except MergeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        candidate.refresh_from_db()
        return Response(DuplicateCandidateSerializer(candidate).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Human confirms these are two different people."""
        candidate = self.get_object()
        serializer = RejectDuplicateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reject_duplicate_candidate(candidate, serializer.validated_data["performed_by"])
        candidate.refresh_from_db()
        return Response(DuplicateCandidateSerializer(candidate).data)


class PersonMergeLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PersonMergeLog.objects.select_related("source_person", "target_person")
    serializer_class = PersonMergeLogSerializer

    @action(detail=True, methods=["post"])
    def revert(self, request, pk=None):
        log = self.get_object()
        performed_by = request.data.get("performed_by", "")
        try:
            revert_merge(log, performed_by)
        except MergeError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        log.refresh_from_db()
        return Response(PersonMergeLogSerializer(log).data)
