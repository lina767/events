from people.models import Person, PersonEmail


def make_person(display_name="Jane Doe", organization="Acme Corp", **kwargs) -> Person:
    return Person.objects.create(display_name=display_name, organization=organization, **kwargs)


def make_email(person: Person, email: str, is_primary: bool = False) -> PersonEmail:
    return PersonEmail.objects.create(person=person, email=email, is_primary=is_primary)
