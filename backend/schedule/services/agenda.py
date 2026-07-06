from schedule.models import PersonalAgendaItem, Session


def add_to_agenda(person, session: Session) -> PersonalAgendaItem:
    item, _ = PersonalAgendaItem.objects.get_or_create(person=person, session=session)
    return item


def remove_from_agenda(person, session: Session) -> None:
    PersonalAgendaItem.objects.filter(person=person, session=session).delete()


def get_agenda(person, event) -> list[Session]:
    """Ordered by current_estimated_start, so a delay reorders the agenda automatically."""
    return list(
        Session.objects.filter(agenda_items__person=person, event=event).order_by(
            "current_estimated_start"
        )
    )
