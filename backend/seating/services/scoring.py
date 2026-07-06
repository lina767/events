"""
score(table) = w1*sector_diversity + w2*seniority_balance + w3*relationship_bonus
             - LARGE_PENALTY*hard_constraint_violations

Each soft term is normalized to roughly [0, 1] so the weights are
comparable and meaningful to tune from a UI slider.
"""

from collections import Counter
from dataclasses import dataclass

LARGE_PENALTY = 1000


@dataclass(frozen=True)
class Weights:
    sector_diversity: float = 1.0
    seniority_balance: float = 1.0
    relationship_bonus: float = 1.0


def sector_diversity(persons) -> float:
    if not persons:
        return 0.0
    distinct = len({tag for p in persons for tag in p.sector_tags})
    return min(1.0, distinct / len(persons))


def seniority_balance(persons) -> float:
    if not persons:
        return 0.0
    counts = Counter(p.seniority_level for p in persons)
    most_common = counts.most_common(1)[0][1]
    return 1 - (most_common / len(persons))


def relationship_bonus(persons, positive_pairs: set[tuple]) -> float:
    ids = {p.person_id for p in persons}
    if len(ids) < 2:
        return 0.0
    hits = sum(1 for pair in positive_pairs if pair[0] in ids and pair[1] in ids)
    possible = len(ids) * (len(ids) - 1) // 2
    return hits / possible


def hard_exclusion_violations(persons, excluded_pairs: set[tuple]) -> int:
    ids = {p.person_id for p in persons}
    return sum(1 for pair in excluded_pairs if pair[0] in ids and pair[1] in ids)


def table_score(persons, positive_pairs, excluded_pairs, weights: Weights) -> float:
    score = (
        weights.sector_diversity * sector_diversity(persons)
        + weights.seniority_balance * seniority_balance(persons)
        + weights.relationship_bonus * relationship_bonus(persons, positive_pairs)
    )
    return score - LARGE_PENALTY * hard_exclusion_violations(persons, excluded_pairs)


def required_pair_violations(assignment: dict, required_pairs: set[tuple]) -> int:
    """Required-together pairs split across different tables - a cross-table concern."""
    return sum(1 for a, b in required_pairs if assignment.get(a) != assignment.get(b))


def explain_table(persons, positive_pairs, excluded_pairs) -> str:
    """A short, human-readable rationale for a table's proposed seating."""
    if not persons:
        return "No guests assigned."

    parts = []
    diversity = sector_diversity(persons)
    if diversity >= 0.7:
        parts.append("high sector diversity")
    elif diversity >= 0.4:
        parts.append("moderate sector diversity")
    else:
        parts.append("low sector diversity")

    balance = seniority_balance(persons)
    parts.append("balanced seniority mix" if balance >= 0.6 else "uneven seniority mix")

    if relationship_bonus(persons, positive_pairs) > 0:
        parts.append("some seated pairs already know each other")

    violations = hard_exclusion_violations(persons, excluded_pairs)
    if violations:
        parts.append(f"WARNING: {violations} conflicting pair(s) at this table")

    return ", ".join(parts)
