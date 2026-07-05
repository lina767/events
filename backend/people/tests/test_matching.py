from django.test import TestCase

from people.models import DuplicateCandidate, normalize_name
from people.services.matching import score_pair
from people.tests.factories import make_email, make_person


class NormalizeNameTests(TestCase):
    def test_strips_diacritics_case_and_punctuation(self):
        self.assertEqual(normalize_name("François Müller-Schmidt"), "francois muller schmidt")

    def test_collapses_whitespace(self):
        self.assertEqual(normalize_name("  Jane   Doe  "), "jane doe")


class ScorePairTests(TestCase):
    def test_identical_names_score_high(self):
        a = make_person(display_name="Jane Doe")
        b = make_person(display_name="Jane Doe")
        result = score_pair(a, b)
        self.assertIsNotNone(result)
        self.assertEqual(result.score, 100)

    def test_unrelated_names_are_not_matched(self):
        a = make_person(display_name="Jane Doe")
        b = make_person(display_name="Robert Fischer")
        self.assertIsNone(score_pair(a, b))

    def test_shared_corporate_email_domain_boosts_score(self):
        a = make_person(display_name="Jane Doe", organization="")
        b = make_person(display_name="Jane Doh", organization="")
        make_email(a, "jane.doe@acme-corp.com")
        make_email(b, "j.doe@acme-corp.com")
        result = score_pair(a, b)
        self.assertIsNotNone(result)
        self.assertTrue(any("domain" in reason for reason in result.reasons))

    def test_shared_generic_public_domain_is_not_a_signal(self):
        a = make_person(display_name="Jane Doe")
        b = make_person(display_name="Jane Doh")
        make_email(a, "jane.doe@gmail.com")
        make_email(b, "jane.doh@gmail.com")
        result = score_pair(a, b)
        self.assertIsNotNone(result)
        self.assertFalse(any("domain" in reason for reason in result.reasons))

    def test_matching_organization_boosts_score(self):
        a = make_person(display_name="Jane Doe", organization="Acme Corporation")
        b = make_person(display_name="Jane Doh", organization="Acme Corporation")
        result = score_pair(a, b)
        self.assertIsNotNone(result)
        self.assertTrue(any("organization" in reason for reason in result.reasons))


class DuplicateCandidateCreationTests(TestCase):
    def test_creating_a_similar_person_generates_a_pending_candidate(self):
        make_person(display_name="Jane Doe")
        make_person(display_name="Jane Doe")  # triggers post_save signal

        self.assertEqual(DuplicateCandidate.objects.count(), 1)
        candidate = DuplicateCandidate.objects.get()
        self.assertEqual(candidate.status, "pending")
        self.assertEqual(candidate.confidence_score, 100)

    def test_no_candidate_for_dissimilar_people(self):
        make_person(display_name="Jane Doe")
        make_person(display_name="Robert Fischer")

        self.assertEqual(DuplicateCandidate.objects.count(), 0)

    def test_pair_is_deduplicated_regardless_of_creation_order(self):
        a = make_person(display_name="Jane Doe")
        b = make_person(display_name="Jane Doe")

        # Re-running matching manually (e.g. via scan_duplicates) must not
        # create a second row for the same pair in reverse order.
        from people.services.matching import find_duplicate_candidates

        find_duplicate_candidates(a)
        find_duplicate_candidates(b)

        self.assertEqual(DuplicateCandidate.objects.count(), 1)

    def test_rejected_candidate_is_not_resurrected_by_rescan(self):
        from people.services.matching import find_duplicate_candidates
        from people.services.merging import reject_duplicate_candidate

        a = make_person(display_name="Jane Doe")
        make_person(display_name="Jane Doe")
        candidate = DuplicateCandidate.objects.get()
        reject_duplicate_candidate(candidate, performed_by="reviewer@example.com")

        find_duplicate_candidates(a)

        candidate.refresh_from_db()
        self.assertEqual(candidate.status, "rejected")
        self.assertEqual(DuplicateCandidate.objects.count(), 1)
