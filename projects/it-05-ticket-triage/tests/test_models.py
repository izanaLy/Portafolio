import pytest

from ticket_triage.models import Level, Priority, Ticket


def valid(**overrides):
    data = {"id": "T-1", "title": "Titulo", "description": "Descripcion"}
    data.update(overrides)
    return data


def test_from_dict_applies_defaults():
    ticket = Ticket.from_dict(valid())
    assert ticket.affected_users == 1
    assert ticket.workaround_available is None
    assert ticket.requester == "usuario-desconocido"
    assert ticket.created_at is None


def test_from_dict_strips_whitespace():
    ticket = Ticket.from_dict(valid(id="  T-9 ", title=" a ", description=" b "))
    assert (ticket.id, ticket.title, ticket.description) == ("T-9", "a", "b")


@pytest.mark.parametrize("field", ["id", "title", "description"])
@pytest.mark.parametrize("bad", [None, "", "   ", 5])
def test_required_text_fields_are_validated(field, bad):
    with pytest.raises(ValueError):
        Ticket.from_dict(valid(**{field: bad}))


@pytest.mark.parametrize("bad", [0, -3, 1.5, "2", True, None])
def test_affected_users_must_be_positive_int(bad):
    with pytest.raises(ValueError):
        Ticket.from_dict(valid(affected_users=bad))


@pytest.mark.parametrize("bad", ["si", 1, 0])
def test_workaround_must_be_bool_or_none(bad):
    with pytest.raises(ValueError):
        Ticket.from_dict(valid(workaround_available=bad))


def test_created_at_must_be_text():
    with pytest.raises(ValueError):
        Ticket.from_dict(valid(created_at=20260105))


def test_level_and_priority_ordering_and_labels():
    assert Level.LOW < Level.MEDIUM < Level.HIGH
    assert Priority.P1 < Priority.P4  # P1 es la más alta (valor numérico menor)
    assert [lvl.label for lvl in Level] == ["bajo", "medio", "alto"]
    assert Priority.P2.label == "P2"
    assert Level.from_label("alto") is Level.HIGH
    with pytest.raises(ValueError):
        Level.from_label("critico")
