"""
Networking reuses the Golden Record directly instead of a separate
profile model - name, organization, and sector tags already live on
Person, and search/filter is enough for v1.
"""

from django.db.models import Q

from invitations.services.capacity import accepted_attendees


def search_attendees(event, query: str = "", sector_tag: str = ""):
    attendees = accepted_attendees(event)
    if query:
        attendees = attendees.filter(
            Q(display_name__icontains=query) | Q(organization__icontains=query)
        )
    if sector_tag:
        attendees = attendees.filter(sector_tags__contains=[sector_tag])
    return attendees
