"""
Duplicate-candidate detection for the Golden Record.

Deliberately no auto-merge: this module only ever proposes
DuplicateCandidate rows for a human to confirm or reject. A false
auto-merge on a diplomat/VIP record is worse than a visible duplicate.
"""

from dataclasses import dataclass

from django.conf import settings
from django.db import transaction
from rapidfuzz import fuzz

from people.models import DuplicateCandidate, DuplicateCandidateStatus, Person

# Below this raw name-similarity score we don't even consider a pair -
# email/org overlap alone should not be enough to flag two different people.
MINIMUM_NAME_SIMILARITY = 60

EMAIL_DOMAIN_BONUS = 15
ORGANIZATION_BONUS = 10
ORGANIZATION_FUZZY_THRESHOLD = 85


@dataclass
class MatchResult:
    score: int
    reasons: list[str]


def _shared_email_domains(person_a: Person, person_b: Person) -> bool:
    domains_a = {e.domain for e in person_a.emails.all() if e.domain}
    domains_b = {e.domain for e in person_b.emails.all() if e.domain}
    # Skip generic public providers - a shared gmail.com is not a signal.
    generic = {"gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "web.de", "gmx.de", "icloud.com"}
    return bool((domains_a & domains_b) - generic)


def score_pair(person_a: Person, person_b: Person) -> MatchResult | None:
    """Return a MatchResult if the pair looks like a plausible duplicate, else None."""
    name_score = fuzz.token_sort_ratio(person_a.normalized_name, person_b.normalized_name)
    if name_score < MINIMUM_NAME_SIMILARITY:
        return None

    reasons = [f"Namensähnlichkeit: {round(name_score)}%"]
    bonus = 0

    if _shared_email_domains(person_a, person_b):
        bonus += EMAIL_DOMAIN_BONUS
        reasons.append("gemeinsame E-Mail-Domain (nicht öffentlicher Anbieter)")

    if person_a.organization and person_b.organization:
        org_score = fuzz.token_sort_ratio(
            person_a.organization.lower(), person_b.organization.lower()
        )
        if org_score >= ORGANIZATION_FUZZY_THRESHOLD:
            bonus += ORGANIZATION_BONUS
            reasons.append("gleiche Organisation")

    score = min(100, round(name_score + bonus))
    return MatchResult(score=score, reasons=reasons)


def _ordered_pair(person_a: Person, person_b: Person):
    """Stable ordering so (a, b) and (b, a) always dedupe to the same row."""
    if str(person_a.person_id) <= str(person_b.person_id):
        return person_a, person_b
    return person_b, person_a


def _upsert_candidate(person_a: Person, person_b: Person, result: MatchResult):
    """
    Create a pending candidate, or refresh the score on an existing pending
    one. A pair a human already decided on (confirmed/rejected) is left
    alone - a rescan should not resurrect a rejected "not a duplicate" call.
    """
    first, second = _ordered_pair(person_a, person_b)
    existing = DuplicateCandidate.objects.filter(person_a=first, person_b=second).first()
    if existing is None:
        return DuplicateCandidate.objects.create(
            person_a=first,
            person_b=second,
            confidence_score=result.score,
            reasons=result.reasons,
        )
    if existing.status == DuplicateCandidateStatus.PENDING:
        existing.confidence_score = result.score
        existing.reasons = result.reasons
        existing.save(update_fields=["confidence_score", "reasons"])
    return existing


@transaction.atomic
def find_duplicate_candidates(
    person: Person, threshold: int | None = None
) -> list[DuplicateCandidate]:
    """
    Compare `person` against all other active Persons and create/update
    pending DuplicateCandidate rows for matches at or above the threshold.
    Called on create of a new Person (import, manual entry, email parsing).
    """
    if threshold is None:
        threshold = settings.GOLDEN_RECORD_DUPLICATE_THRESHOLD

    candidates = []
    others = Person.objects.filter(is_active=True).exclude(person_id=person.person_id)
    for other in others:
        result = score_pair(person, other)
        if result is None or result.score < threshold:
            continue

        candidate = _upsert_candidate(person, other, result)
        candidates.append(candidate)
    return candidates


def scan_all_for_duplicates(threshold: int | None = None) -> int:
    """
    Batch cleanup mode: pairwise-compare all active Persons. O(n^2), which
    is fine for the thousands-of-records scale this system targets - not
    millions. Intended to be run once as a management command, not per
    request.
    """
    if threshold is None:
        threshold = settings.GOLDEN_RECORD_DUPLICATE_THRESHOLD

    created_or_updated = 0
    people = list(Person.objects.filter(is_active=True))
    for i, person_a in enumerate(people):
        for person_b in people[i + 1 :]:
            result = score_pair(person_a, person_b)
            if result is None or result.score < threshold:
                continue
            _upsert_candidate(person_a, person_b, result)
            created_or_updated += 1
    return created_or_updated
