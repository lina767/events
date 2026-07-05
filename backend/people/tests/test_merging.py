from django.test import TestCase

from people.models import DuplicateCandidate, DuplicateCandidateStatus, PersonMergeLog
from people.services.merging import MergeError, merge_persons, revert_merge
from people.tests.factories import make_email, make_person


class MergePersonsTests(TestCase):
    def test_merge_deactivates_source_and_points_to_target(self):
        source = make_person(display_name="Jane Doe")
        target = make_person(display_name="Jane Doe")

        merge_persons(source=source, target=target, performed_by="reviewer@example.com")

        source.refresh_from_db()
        self.assertFalse(source.is_active)
        self.assertEqual(source.merged_into_id, target.person_id)

    def test_merge_moves_emails_to_target(self):
        source = make_person(display_name="Jane Doe")
        target = make_person(display_name="Jane Doe")
        make_email(source, "jane@source.example", is_primary=True)

        merge_persons(source=source, target=target, performed_by="reviewer@example.com")

        self.assertEqual(target.emails.count(), 1)
        self.assertEqual(source.emails.count(), 0)

    def test_merge_avoids_two_primary_emails_on_target(self):
        source = make_person(display_name="Jane Doe")
        target = make_person(display_name="Jane Doe")
        make_email(source, "jane@source.example", is_primary=True)
        make_email(target, "jane@target.example", is_primary=True)

        merge_persons(source=source, target=target, performed_by="reviewer@example.com")

        self.assertEqual(target.emails.filter(is_primary=True).count(), 1)
        moved = target.emails.get(email="jane@source.example")
        self.assertFalse(moved.is_primary)

    def test_merge_logs_moved_email_ids_for_revert(self):
        source = make_person(display_name="Jane Doe")
        target = make_person(display_name="Jane Doe")
        email = make_email(source, "jane@source.example", is_primary=True)

        log = merge_persons(source=source, target=target, performed_by="reviewer@example.com")

        self.assertEqual(log.moved_emails, [{"id": email.id, "was_primary": True}])

    def test_cannot_merge_person_with_self(self):
        person = make_person(display_name="Jane Doe")
        with self.assertRaises(MergeError):
            merge_persons(source=person, target=person, performed_by="reviewer@example.com")

    def test_cannot_merge_already_inactive_source(self):
        source = make_person(display_name="Jane Doe")
        target = make_person(display_name="Jane Doe")
        other_target = make_person(display_name="Jane Doe")
        merge_persons(source=source, target=target, performed_by="reviewer@example.com")

        with self.assertRaises(MergeError):
            merge_persons(source=source, target=other_target, performed_by="reviewer@example.com")

    def test_confirming_a_merge_marks_only_candidates_touching_the_source_obsolete(self):
        # Three mutually similar people form a triangle of 3 candidate pairs.
        a = make_person(display_name="Jane Doe")
        b = make_person(display_name="Jane Doe")
        c = make_person(display_name="Jane Doe")

        candidate_ab = DuplicateCandidate.objects.get(
            person_a__in=[a, b], person_b__in=[a, b]
        )
        candidate_bc = DuplicateCandidate.objects.get(
            person_a__in=[b, c], person_b__in=[b, c]
        )

        merge_persons(
            source=b,
            target=a,
            performed_by="reviewer@example.com",
            duplicate_candidate=candidate_ab,
        )

        candidate_ab.refresh_from_db()
        candidate_bc.refresh_from_db()
        self.assertEqual(candidate_ab.status, DuplicateCandidateStatus.CONFIRMED)
        # b is now inactive, so the b<->c pair is a dead question - obsolete.
        self.assertEqual(candidate_bc.status, DuplicateCandidateStatus.OBSOLETE)
        # a<->c is still a live, undecided pair between two active people.
        candidate_ac = DuplicateCandidate.objects.get(
            person_a__in=[a, c], person_b__in=[a, c]
        )
        self.assertEqual(candidate_ac.status, DuplicateCandidateStatus.PENDING)


class RevertMergeTests(TestCase):
    def test_revert_reactivates_source_and_moves_emails_back(self):
        source = make_person(display_name="Jane Doe")
        target = make_person(display_name="Jane Doe")
        make_email(source, "jane@source.example", is_primary=True)

        log = merge_persons(source=source, target=target, performed_by="reviewer@example.com")
        revert_merge(log, performed_by="reviewer@example.com")

        source.refresh_from_db()
        self.assertTrue(source.is_active)
        self.assertIsNone(source.merged_into)
        self.assertEqual(source.emails.get().email, "jane@source.example")
        self.assertTrue(source.emails.get().is_primary)
        self.assertEqual(target.emails.count(), 0)

    def test_cannot_revert_twice(self):
        source = make_person(display_name="Jane Doe")
        target = make_person(display_name="Jane Doe")
        log = merge_persons(source=source, target=target, performed_by="reviewer@example.com")
        revert_merge(log, performed_by="reviewer@example.com")

        with self.assertRaises(MergeError):
            revert_merge(log, performed_by="reviewer@example.com")

    def test_revert_reopens_linked_duplicate_candidate(self):
        make_person(display_name="Jane Doe")
        make_person(display_name="Jane Doe")
        candidate = DuplicateCandidate.objects.get()
        source, target = candidate.person_b, candidate.person_a

        log = merge_persons(
            source=source,
            target=target,
            performed_by="reviewer@example.com",
            duplicate_candidate=candidate,
        )
        revert_merge(log, performed_by="reviewer@example.com")

        candidate.refresh_from_db()
        self.assertEqual(candidate.status, DuplicateCandidateStatus.PENDING)

    def test_revert_log_is_queryable_afterwards(self):
        source = make_person(display_name="Jane Doe")
        target = make_person(display_name="Jane Doe")
        log = merge_persons(source=source, target=target, performed_by="reviewer@example.com")
        revert_merge(log, performed_by="reviewer@example.com")

        self.assertEqual(PersonMergeLog.objects.get(pk=log.pk).reverted_by, "reviewer@example.com")
