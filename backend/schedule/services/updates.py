"""
The room-update actions: large one-tap buttons instead of a form, so
correcting the schedule is faster than forgetting to. Every call here
updates in place and stamps last_confirmed_at/by, which is what lets the
traffic light say "confirmed 2 minutes ago" instead of showing a stale
time as if it were still certain.
"""

from django.db import transaction
from django.utils import timezone

from schedule.models import Room, Session, SessionStatus


def _touch(session: Session, confirmed_by: str):
    session.last_confirmed_at = timezone.now()
    session.last_confirmed_by = confirmed_by


def confirm_on_time(session: Session, confirmed_by: str) -> Session:
    session.status = SessionStatus.CONFIRMED
    _touch(session, confirmed_by)
    session.save(update_fields=["status", "last_confirmed_at", "last_confirmed_by"])
    return session


def delay(session: Session, minutes: int, confirmed_by: str) -> Session:
    session.status = SessionStatus.DELAYED
    session.current_estimated_start = session.current_estimated_start + timezone.timedelta(
        minutes=minutes
    )
    _touch(session, confirmed_by)
    session.save(
        update_fields=[
            "status",
            "current_estimated_start",
            "last_confirmed_at",
            "last_confirmed_by",
        ]
    )
    return session


def mark_running(session: Session, confirmed_by: str) -> Session:
    session.status = SessionStatus.RUNNING
    _touch(session, confirmed_by)
    session.save(update_fields=["status", "last_confirmed_at", "last_confirmed_by"])
    return session


def cancel(session: Session, confirmed_by: str) -> Session:
    session.status = SessionStatus.CANCELLED
    _touch(session, confirmed_by)
    session.save(update_fields=["status", "last_confirmed_at", "last_confirmed_by"])
    return session


def subsequent_sessions_in_room(session: Session) -> list[Session]:
    """What a delay could cascade into - shown as a one-tap suggestion, never forced."""
    return list(
        Session.objects.filter(
            room=session.room, scheduled_start__gt=session.scheduled_start
        ).exclude(pk=session.pk)
    )


@transaction.atomic
def apply_shift_to_sessions(sessions: list[Session], minutes: int, confirmed_by: str) -> list[Session]:
    """Bulk-apply the same delay to a confirmed set of subsequent sessions."""
    for session in sessions:
        delay(session, minutes, confirmed_by)
    return sessions


def current_and_next_session(room: Room) -> tuple[Session | None, Session | None]:
    """What the no-login room-update page shows: today's live state, nothing else."""
    now = timezone.now()
    sessions = list(
        Session.objects.filter(room=room)
        .exclude(status=SessionStatus.CANCELLED)
        .order_by("scheduled_start")
    )
    current = next((s for s in sessions if s.status == SessionStatus.RUNNING), None)
    if current is None:
        past = [s for s in sessions if s.scheduled_start <= now]
        current = past[-1] if past else None

    anchor = current.scheduled_start if current else now
    upcoming = [s for s in sessions if s.scheduled_start > anchor]
    next_session = upcoming[0] if upcoming else None
    return current, next_session
