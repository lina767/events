"""
Groups duplicate nominations for the same nominee so they're reviewed and
decided together, instead of one nominator's proposal getting approved
while another's identical proposal sits forgotten in the queue.
"""

from people.models import normalize_name

from nominations.models import Nomination, NominationStatus


def _group_key(nomination: Nomination):
    if nomination.nominee_id:
        return ("person", nomination.nominee_id)
    return ("name", normalize_name(nomination.nominee_name))


def group_pending(event) -> list[list[Nomination]]:
    """All open nominations for an event, bundled by resolved/likely nominee."""
    open_nominations = list(
        Nomination.objects.filter(event=event, status=NominationStatus.OPEN).select_related(
            "nominee", "nominator"
        )
    )
    groups: dict[tuple, list[Nomination]] = {}
    for nomination in open_nominations:
        groups.setdefault(_group_key(nomination), []).append(nomination)
    return list(groups.values())


def find_group(nomination: Nomination) -> list[Nomination]:
    """All still-open nominations that name the same nominee as `nomination`."""
    key = _group_key(nomination)
    same_event_open = Nomination.objects.filter(
        event_id=nomination.event_id, status=NominationStatus.OPEN
    )
    group = [n for n in same_event_open if _group_key(n) == key]
    if nomination not in group:
        group.append(nomination)
    return group
