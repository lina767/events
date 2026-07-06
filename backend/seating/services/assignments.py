"""
Orchestrates the optimizer against real data and persists its output as
TableAssignment proposals. Nothing here ever marks a plan final - see
confirm_event_seating().
"""

from collections import Counter

from django.db import transaction
from django.utils import timezone

from invitations.services.capacity import accepted_attendees

from seating.models import Table, TableAssignment
from seating.services.annealing import optimize


def _existing_assignment(event) -> dict:
    return dict(TableAssignment.objects.filter(event=event).values_list("person_id", "table_id"))


@transaction.atomic
def run_full_optimization(event, iterations: int = 1500, seed: int | None = None) -> list[TableAssignment]:
    """A full re-run over every table - the initial seating plan, or a deliberate reshuffle."""
    guests = list(accepted_attendees(event))
    result = optimize(
        event,
        guests,
        existing_assignment=_existing_assignment(event),
        iterations=iterations,
        seed=seed,
    )
    return _persist(event, result)


@transaction.atomic
def run_local_reoptimization(
    event, changed_person_ids: list, iterations: int = 500, seed: int | None = None
) -> list[TableAssignment]:
    """
    Reoptimizes only the table(s) a change touched (e.g. a decline freed a
    seat) plus up to two neighboring tables with spare capacity - not a
    global re-run over every table, so guests at unrelated tables are
    never disturbed by someone else's cancellation.
    """
    changed_person_ids = set(changed_person_ids)
    tables = list(Table.objects.filter(event=event))
    assignments = list(TableAssignment.objects.filter(event=event))
    capacity_used = Counter(a.table_id for a in assignments)

    touched_table_ids = {a.table_id for a in assignments if a.person_id in changed_person_ids}
    by_free_capacity = sorted(
        tables, key=lambda t: t.capacity - capacity_used.get(t.id, 0), reverse=True
    )
    neighbor_ids = [t.id for t in by_free_capacity if t.id not in touched_table_ids][:2]
    scope_table_ids = touched_table_ids | set(neighbor_ids)

    guest_ids_in_scope = {a.person_id for a in assignments if a.table_id in scope_table_ids}
    guest_ids = guest_ids_in_scope | changed_person_ids

    accepted_by_id = {g.person_id: g for g in accepted_attendees(event)}
    guests = [accepted_by_id[pid] for pid in guest_ids if pid in accepted_by_id]

    result = optimize(
        event,
        guests,
        scope_table_ids=scope_table_ids,
        existing_assignment=_existing_assignment(event),
        iterations=iterations,
        seed=seed,
    )
    return _persist(event, result)


def _persist(event, result: dict) -> list[TableAssignment]:
    updated = []
    for person_id, table_id in result["assignment"].items():
        assignment, _created = TableAssignment.objects.update_or_create(
            event=event,
            person_id=person_id,
            defaults={
                "table_id": table_id,
                "rationale": result["explanations"].get(table_id, ""),
                "is_confirmed": False,
                "confirmed_by": "",
                "confirmed_at": None,
            },
        )
        updated.append(assignment)
    return updated


def confirm_event_seating(event, confirmed_by: str) -> int:
    """The explicit human sign-off required before a plan is communicated to guests."""
    return TableAssignment.objects.filter(event=event, is_confirmed=False).update(
        is_confirmed=True, confirmed_by=confirmed_by, confirmed_at=timezone.now()
    )
