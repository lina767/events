from events.tests.factories import make_event
from people.tests.factories import make_person

from nominations.models import Nomination


def make_nomination(event=None, nominator=None, nominee=None, nominee_name="", **kwargs) -> Nomination:
    return Nomination.objects.create(
        event=event or make_event(),
        nominator=nominator or make_person(display_name="Staff Member"),
        nominee=nominee,
        nominee_name=nominee_name,
        **kwargs,
    )
