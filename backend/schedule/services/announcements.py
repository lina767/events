from django.db.models import Q

from schedule.models import Announcement


def create_announcement(
    event, message: str, created_by: str, audience_sector_tag: str = ""
) -> Announcement:
    return Announcement.objects.create(
        event=event, message=message, created_by=created_by, audience_sector_tag=audience_sector_tag
    )


def list_announcements(event, for_sector_tag: str = "", since=None) -> list[Announcement]:
    """
    Announcements for everyone, plus ones targeted at `for_sector_tag`
    (e.g. the caller's own track) - never announcements meant for a
    *different* track.
    """
    qs = Announcement.objects.filter(event=event)
    if for_sector_tag:
        qs = qs.filter(Q(audience_sector_tag="") | Q(audience_sector_tag=for_sector_tag))
    else:
        qs = qs.filter(audience_sector_tag="")
    if since:
        qs = qs.filter(created_at__gt=since)
    return list(qs)
