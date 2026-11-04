"""Carga de conjuntos de datos de tickets desde JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Union

from .models import Ticket

DEFAULT_DATASET = Path(__file__).resolve().parent.parent / "data" / "synthetic_tickets.json"


@dataclass(frozen=True)
class Dataset:
    meta: Dict[str, Any]
    tickets: List[Ticket]
    # Etiquetas esperadas, solo para pruebas de regresión (id -> etiquetas).
    expected: Dict[str, Dict[str, str]]


def load_dataset(path: Union[str, Path] = DEFAULT_DATASET) -> Dataset:
    """Lee un archivo con ``{"meta": {...}, "tickets": [...]}``.

    Exige ``meta.synthetic == true`` para evitar cargar datos reales por error.
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "tickets" not in raw:
        raise ValueError("El archivo debe ser un objeto JSON con la clave 'tickets'")

    meta = raw.get("meta", {})
    if meta.get("synthetic") is not True:
        raise ValueError(
            "El conjunto de datos debe declarar meta.synthetic = true "
            "(este proyecto solo usa datos sintéticos)"
        )

    tickets: List[Ticket] = []
    expected: Dict[str, Dict[str, str]] = {}
    seen = set()
    for item in raw["tickets"]:
        ticket = Ticket.from_dict(item)
        if ticket.id in seen:
            raise ValueError(f"ID de ticket duplicado: {ticket.id!r}")
        seen.add(ticket.id)
        tickets.append(ticket)
        if "expected" in item:
            expected[ticket.id] = dict(item["expected"])
    return Dataset(meta=meta, tickets=tickets, expected=expected)
