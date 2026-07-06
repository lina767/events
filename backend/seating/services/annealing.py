"""
Simulated annealing with warm start: the search always begins from the
currently assigned tables, not an empty room, and (via scope_table_ids)
can be restricted to just the tables touched by a change plus a couple of
neighbors - a local reoptimization instead of a full 30-table re-run.
"""

import math
import random
from collections import defaultdict

from people.models import Person

from seating.models import RelationshipEdge, RelationshipType, SeatingWeights, SeatPin, Table
from seating.services.scoring import (
    LARGE_PENALTY,
    Weights,
    explain_table,
    required_pair_violations,
    table_score,
)


def _weights_for(event) -> Weights:
    try:
        w = event.seating_weights
    except SeatingWeights.DoesNotExist:
        return Weights()
    return Weights(
        sector_diversity=float(w.sector_diversity),
        seniority_balance=float(w.seniority_balance),
        relationship_bonus=float(w.relationship_bonus),
    )


def _relationship_pairs(person_ids):
    edges = RelationshipEdge.objects.filter(person_a_id__in=person_ids, person_b_id__in=person_ids)
    positive, excluded, required = set(), set(), set()
    for edge in edges:
        pair = (edge.person_a_id, edge.person_b_id)
        if edge.edge_type == RelationshipType.POSITIVE:
            positive.add(pair)
            if edge.is_hard_constraint:
                required.add(pair)
        else:
            excluded.add(pair)
    return positive, excluded, required


def _total_score(assignment, persons_by_id, positive, excluded, required, weights):
    by_table = defaultdict(list)
    for person_id, table_id in assignment.items():
        by_table[table_id].append(persons_by_id[person_id])
    total = sum(table_score(members, positive, excluded, weights) for members in by_table.values())
    total -= LARGE_PENALTY * required_pair_violations(assignment, required)
    return total


def optimize(
    event,
    guests: list[Person],
    *,
    scope_table_ids: set[int] | None = None,
    existing_assignment: dict | None = None,
    iterations: int = 1500,
    seed: int | None = None,
) -> dict:
    """
    Returns {"assignment": {person_id: table_id}, "score": float,
    "explanations": {table_id: str}} for the given guest pool. Only ever
    moves guests within scope_table_ids when one is given.
    """
    rng = random.Random(seed)
    tables = list(Table.objects.filter(event=event))
    scope_ids = scope_table_ids or {t.id for t in tables}

    persons_by_id = {g.person_id: g for g in guests}
    guest_ids = set(persons_by_id)

    pins = {
        p.person_id: p.table_id
        for p in SeatPin.objects.filter(event=event, person_id__in=guest_ids)
    }
    existing_assignment = existing_assignment or {}

    positive, excluded, required = _relationship_pairs(guest_ids)

    assignment: dict = {}
    capacity_used = {t.id: 0 for t in tables}

    def _place(person_id, table_id):
        assignment[person_id] = table_id
        capacity_used[table_id] += 1

    unplaced = []
    for person_id in guest_ids:
        if person_id in pins:
            _place(person_id, pins[person_id])
        elif existing_assignment.get(person_id) in scope_ids:
            _place(person_id, existing_assignment[person_id])
        else:
            unplaced.append(person_id)

    def _tables_with_room():
        return [t.id for t in tables if t.id in scope_ids and capacity_used[t.id] < t.capacity]

    for person_id in unplaced:
        candidates = _tables_with_room()
        if not candidates and scope_ids:
            # Scope is over capacity - seat anyway at the least-full table so
            # the optimizer has a starting point; a human resolves genuine
            # overbooking before confirming, this just avoids losing a guest.
            candidates = [min(scope_ids, key=lambda tid: capacity_used[tid])]
        if candidates:
            _place(person_id, rng.choice(candidates))

    movable_ids = [pid for pid in guest_ids if pid not in pins]

    weights = _weights_for(event)
    best_assignment = dict(assignment)
    best_score = _total_score(assignment, persons_by_id, positive, excluded, required, weights)
    current_score = best_score

    temperature = 1.0
    cooling = 0.995

    for _ in range(iterations):
        if len(movable_ids) < 2:
            break
        a, b = rng.sample(movable_ids, 2)
        if assignment[a] == assignment[b]:
            continue

        assignment[a], assignment[b] = assignment[b], assignment[a]
        new_score = _total_score(assignment, persons_by_id, positive, excluded, required, weights)
        delta = new_score - current_score

        if delta >= 0 or rng.random() < math.exp(delta / max(temperature, 1e-6)):
            current_score = new_score
            if new_score > best_score:
                best_score = new_score
                best_assignment = dict(assignment)
        else:
            assignment[a], assignment[b] = assignment[b], assignment[a]

        temperature *= cooling

    explanations = {
        table_id: explain_table(
            [persons_by_id[pid] for pid, tid in best_assignment.items() if tid == table_id],
            positive,
            excluded,
        )
        for table_id in scope_ids
    }

    return {"assignment": best_assignment, "score": best_score, "explanations": explanations}
