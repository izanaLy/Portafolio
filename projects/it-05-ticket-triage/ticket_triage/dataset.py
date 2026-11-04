"""Carga de conjuntos de datos de tickets desde JSON.

Toda entrada inválida se informa con ``ValueError`` y un mensaje que indica
dónde está el problema, para que el CLI pueda devolver el código de salida 2
sin trazas de error.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Union

from .models import Ticket

DEFAULT_DATASET = Path(__file__).resolve().parent.parent / "data" / "synthetic_tickets.json"

# Claves permitidas en el bloque opcional "expected" de cada ticket.
EXPECTED_KEYS = frozenset(
    {"category", "impact", "urgency", "priority", "escalation_level"}
)


@dataclass(frozen=True)
class Dataset:
    meta: Dict[str, Any]
    tickets: List[Ticket]
    # Etiquetas esperadas, solo para pruebas de regresión (id -> etiquetas).
    expected: Dict[str, Dict[str, str]]


def _type_name(value: Any) -> str:
    return "null" if value is None else type(value).__name__


def _parse_expected(value: Any, where: str) -> Dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(
            f"{where}: 'expected' debe ser un objeto de etiquetas, no {_type_name(value)}"
        )
    unknown = sorted(set(value) - EXPECTED_KEYS)
    if unknown:
        raise ValueError(
            f"{where}: claves no permitidas en 'expected': {', '.join(map(repr, unknown))} "
            f"(permitidas: {', '.join(sorted(EXPECTED_KEYS))})"
        )
    for key, label in value.items():
        if not isinstance(label, str) or not label.strip():
            raise ValueError(
                f"{where}: la etiqueta 'expected.{key}' debe ser texto no vacío, "
                f"no {_type_name(label)}"
            )
    return dict(value)


def parse_dataset(raw: Any) -> Dataset:
    """Valida y convierte el contenido ya leído de un JSON en un ``Dataset``.

    Exige ``meta.synthetic == true`` para evitar cargar datos reales por error.
    """
    if not isinstance(raw, dict):
        raise ValueError(
            f"El archivo debe ser un objeto JSON con la clave 'tickets', no {_type_name(raw)}"
        )

    if "meta" not in raw:
        raise ValueError("Falta la clave 'meta' (debe declarar meta.synthetic = true)")
    meta = raw["meta"]
    if not isinstance(meta, dict):
        raise ValueError(f"'meta' debe ser un objeto JSON, no {_type_name(meta)}")
    if meta.get("synthetic") is not True:
        raise ValueError(
            "El conjunto de datos debe declarar meta.synthetic = true "
            "(este proyecto solo usa datos sintéticos)"
        )

    if "tickets" not in raw:
        raise ValueError("Falta la clave 'tickets'")
    items = raw["tickets"]
    if not isinstance(items, list):
        raise ValueError(f"'tickets' debe ser una lista, no {_type_name(items)}")

    tickets: List[Ticket] = []
    expected: Dict[str, Dict[str, str]] = {}
    seen = set()
    for index, item in enumerate(items):
        where = f"tickets[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{where} debe ser un objeto JSON, no {_type_name(item)}")
        try:
            ticket = Ticket.from_dict(item)
        except ValueError as exc:
            raise ValueError(f"{where}: {exc}") from None
        if ticket.id in seen:
            raise ValueError(f"ID de ticket duplicado: {ticket.id!r}")
        seen.add(ticket.id)
        tickets.append(ticket)
        if "expected" in item:
            expected[ticket.id] = _parse_expected(item["expected"], where)
    return Dataset(meta=meta, tickets=tickets, expected=expected)


def load_dataset(path: Union[str, Path] = DEFAULT_DATASET) -> Dataset:
    """Lee un archivo JSON ``{"meta": {...}, "tickets": [...]}`` y lo valida."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_dataset(raw)
