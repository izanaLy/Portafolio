import json
import re

import pytest

from ticket_triage import load_dataset, triage
from ticket_triage.dataset import DEFAULT_DATASET

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s-]{7,}\d)(?!\d)")
IP_ADDRESS = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


@pytest.fixture(scope="module")
def dataset():
    return load_dataset()


def test_dataset_is_declared_synthetic(dataset):
    assert dataset.meta["synthetic"] is True
    assert "ficticios" in dataset.meta["description"]


def test_dataset_has_enough_variety(dataset):
    results = [triage(t) for t in dataset.tickets]
    assert len(dataset.tickets) >= 20
    assert len({r.category for r in results}) >= 8  # todas las categorías + otros
    assert {r.priority.label for r in results} == {"P1", "P2", "P3", "P4"}


def test_ticket_ids_are_unique(dataset):
    ids = [t.id for t in dataset.tickets]
    assert len(ids) == len(set(ids))


def test_requesters_are_pseudonymous(dataset):
    assert all(re.fullmatch(r"usuario-\d{3}", t.requester) for t in dataset.tickets)


def test_no_personal_data_patterns(dataset):
    # Se revisan solo los campos de texto libre; created_at contiene fechas ISO
    # que un patrón de teléfono confundiría con números.
    free_text = "\n".join(
        f"{t.title}\n{t.description}\n{t.requester}" for t in dataset.tickets
    )
    assert not EMAIL.search(free_text), "no debe haber correos electrónicos"
    assert not PHONE.search(free_text), "no debe haber teléfonos"
    assert not IP_ADDRESS.search(free_text), "no debe haber direcciones IP"


def test_pii_patterns_do_detect_obvious_cases():
    """Evita que la prueba anterior pase en vacío por patrones mal escritos."""
    assert EMAIL.search("escribir a persona@ejemplo.com")
    assert PHONE.search("llamar al 8888 1234")
    assert PHONE.search("llamar al +506 8888-1234")
    assert IP_ADDRESS.search("el equipo 192.168.1.10")


def test_every_ticket_has_expected_labels(dataset):
    assert set(dataset.expected) == {t.id for t in dataset.tickets}


def test_regression_against_expected_labels(dataset):
    """Prueba de regresión: las reglas reproducen las etiquetas definidas por el autor.

    No mide precisión real; solo detecta cambios involuntarios en las reglas.
    """
    mismatches = {}
    for ticket in dataset.tickets:
        actual = triage(ticket).to_dict()
        diff = {
            key: (expected, actual[key])
            for key, expected in dataset.expected[ticket.id].items()
            if actual[key] != expected
        }
        if diff:
            mismatches[ticket.id] = diff
    assert not mismatches, f"Diferencias (esperado, obtenido): {mismatches}"


def _write(tmp_path, payload):
    path = tmp_path / "tickets.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_loader_rejects_datasets_not_declared_synthetic(tmp_path):
    path = _write(tmp_path, {"meta": {}, "tickets": []})
    with pytest.raises(ValueError, match="synthetic"):
        load_dataset(path)


def test_loader_rejects_duplicate_ids(tmp_path):
    ticket = {"id": "X", "title": "t", "description": "d"}
    path = _write(tmp_path, {"meta": {"synthetic": True}, "tickets": [ticket, ticket]})
    with pytest.raises(ValueError, match="duplicado"):
        load_dataset(path)


def test_loader_rejects_missing_tickets_key(tmp_path):
    path = _write(tmp_path, {"meta": {"synthetic": True}})
    with pytest.raises(ValueError, match="tickets"):
        load_dataset(path)
