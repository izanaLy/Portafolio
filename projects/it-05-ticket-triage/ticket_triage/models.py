"""Modelos de datos del simulador de triaje de tickets (IT-05).

El esquema de ``Ticket`` y ``TriageResult`` está pensado para ser reutilizado
por proyectos futuros (``software-09`` Help Desk Portal y ``data-02`` Customer
Support Metrics). Ver la sección «Esquema de ticket» del README.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional


class Level(IntEnum):
    """Nivel ordinal usado para impacto y urgencia."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3

    @property
    def label(self) -> str:
        return {1: "bajo", 2: "medio", 3: "alto"}[int(self)]

    @classmethod
    def from_label(cls, label: str) -> "Level":
        mapping = {"bajo": cls.LOW, "medio": cls.MEDIUM, "alto": cls.HIGH}
        try:
            return mapping[label]
        except KeyError:
            raise ValueError(f"Nivel desconocido: {label!r}") from None


class Priority(IntEnum):
    """Prioridad final. P1 es la más alta."""

    P1 = 1
    P2 = 2
    P3 = 3
    P4 = 4

    @property
    def label(self) -> str:
        return self.name


@dataclass(frozen=True)
class Ticket:
    """Ticket de soporte de entrada.

    Atributos:
        id: identificador único (p. ej. ``TKT-0001``).
        title: resumen corto.
        description: detalle libre escrito por el solicitante.
        requester: identificador seudónimo del solicitante (no usar nombres reales).
        created_at: fecha/hora ISO 8601 (opcional).
        affected_users: número de personas afectadas (>= 1).
        workaround_available: ``True`` si existe una alternativa temporal,
            ``False`` si no existe, ``None`` si no se informó.
    """

    id: str
    title: str
    description: str
    requester: str = "usuario-desconocido"
    created_at: Optional[str] = None
    affected_users: int = 1
    workaround_available: Optional[bool] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Ticket":
        for required in ("id", "title", "description"):
            value = data.get(required)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Campo obligatorio ausente o vacío: {required!r}")

        affected = data.get("affected_users", 1)
        if isinstance(affected, bool) or not isinstance(affected, int) or affected < 1:
            raise ValueError(
                f"affected_users debe ser un entero >= 1 (ticket {data['id']!r})"
            )

        workaround = data.get("workaround_available")
        if workaround is not None and not isinstance(workaround, bool):
            raise ValueError(
                f"workaround_available debe ser true, false o null (ticket {data['id']!r})"
            )

        created_at = data.get("created_at")
        if created_at is not None and not isinstance(created_at, str):
            raise ValueError(f"created_at debe ser texto ISO 8601 (ticket {data['id']!r})")

        return cls(
            id=data["id"].strip(),
            title=data["title"].strip(),
            description=data["description"].strip(),
            requester=str(data.get("requester", "usuario-desconocido")),
            created_at=created_at,
            affected_users=affected,
            workaround_available=workaround,
        )

    @property
    def text(self) -> str:
        """Texto combinado sobre el que se aplican las reglas."""
        return f"{self.title}. {self.description}"


@dataclass(frozen=True)
class TriageResult:
    """Resultado explicable del triaje de un ticket.

    ``escalation_level`` toma uno de ``nivel_1``, ``nivel_2``, ``nivel_3`` (una
    jerarquía) o ``seguridad`` (un canal independiente, no un nivel superior ni
    inferior). ``escalate`` es ``True`` siempre que no sea ``nivel_1``.
    ``escalate_immediately`` depende solo de la prioridad (P1) y es independiente
    del canal: un P1 de seguridad tiene ``escalation_level="seguridad"`` y
    ``escalate_immediately=True``.
    """

    ticket_id: str
    category: str
    impact: Level
    urgency: Level
    priority: Priority
    escalation_level: str
    escalation_team: str
    escalate: bool
    escalate_immediately: bool
    needs_manual_review: bool
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticket_id": self.ticket_id,
            "category": self.category,
            "impact": self.impact.label,
            "urgency": self.urgency.label,
            "priority": self.priority.label,
            "escalation_level": self.escalation_level,
            "escalation_team": self.escalation_team,
            "escalate": self.escalate,
            "escalate_immediately": self.escalate_immediately,
            "needs_manual_review": self.needs_manual_review,
            "reasons": list(self.reasons),
        }
