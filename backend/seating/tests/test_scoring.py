from django.test import TestCase
from people.tests.factories import make_person

from seating.services.scoring import (
    LARGE_PENALTY,
    Weights,
    hard_exclusion_violations,
    relationship_bonus,
    required_pair_violations,
    seniority_balance,
    sector_diversity,
    table_score,
)


class SectorDiversityTests(TestCase):
    def test_all_same_sector_is_low_diversity(self):
        persons = [make_person(sector_tags=["tech"]) for _ in range(4)]
        self.assertEqual(sector_diversity(persons), 0.25)

    def test_all_different_sectors_is_full_diversity(self):
        persons = [make_person(sector_tags=[tag]) for tag in ["tech", "finance", "media", "energy"]]
        self.assertEqual(sector_diversity(persons), 1.0)

    def test_empty_table_is_zero(self):
        self.assertEqual(sector_diversity([]), 0.0)


class SeniorityBalanceTests(TestCase):
    def test_uniform_seniority_is_zero_balance(self):
        persons = [make_person(seniority_level="c_level") for _ in range(4)]
        self.assertEqual(seniority_balance(persons), 0.0)

    def test_evenly_mixed_seniority_is_high_balance(self):
        persons = [
            make_person(seniority_level="c_level"),
            make_person(seniority_level="management"),
            make_person(seniority_level="staff"),
            make_person(seniority_level="senior_executive"),
        ]
        self.assertEqual(seniority_balance(persons), 0.75)


class RelationshipBonusTests(TestCase):
    def test_bonus_counts_pairs_seated_together(self):
        a, b, c = make_person(), make_person(), make_person()
        positive_pairs = {(a.person_id, b.person_id)}
        # 3 guests -> 3 possible pairs, 1 satisfied.
        self.assertAlmostEqual(relationship_bonus([a, b, c], positive_pairs), 1 / 3)

    def test_no_bonus_for_a_lone_guest(self):
        a = make_person()
        self.assertEqual(relationship_bonus([a], set()), 0.0)


class HardExclusionViolationsTests(TestCase):
    def test_counts_conflict_pairs_at_the_same_table(self):
        a, b = make_person(), make_person()
        excluded = {(a.person_id, b.person_id)}
        self.assertEqual(hard_exclusion_violations([a, b], excluded), 1)

    def test_no_violation_when_conflict_pair_not_present(self):
        a, b, c = make_person(), make_person(), make_person()
        excluded = {(a.person_id, b.person_id)}
        self.assertEqual(hard_exclusion_violations([a, c], excluded), 0)


class TableScoreTests(TestCase):
    def test_violation_dominates_the_score(self):
        a, b = make_person(sector_tags=["tech"]), make_person(sector_tags=["finance"])
        excluded = {(a.person_id, b.person_id)}
        score = table_score([a, b], set(), excluded, Weights())
        self.assertLess(score, -LARGE_PENALTY + 10)


class RequiredPairViolationsTests(TestCase):
    def test_split_required_pair_counts_as_a_violation(self):
        assignment = {"a": 1, "b": 2}
        self.assertEqual(required_pair_violations(assignment, {("a", "b")}), 1)

    def test_seated_together_required_pair_is_fine(self):
        assignment = {"a": 1, "b": 1}
        self.assertEqual(required_pair_violations(assignment, {("a", "b")}), 0)
