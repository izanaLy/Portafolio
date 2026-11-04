"""Orquesta las reglas y produce un ``TriageResult`` explicable por ticket."""

from __future__ import annotations

from collections import Counter
from typing import Dict, Iterable, List

from . import rules
from .models import Priority, Ticket, TriageResult


def triage(ticket: Ticket) -> TriageResult:
    """Aplica categoría -> impacto -> urgencia -> prioridad -> escalación."""
    text = rules.normalize(ticket.text)
    reasons: List[str] = []

    category, matches = rules.classify_category(text)
    if matches:
        reasons.append(
            f"categoría «{category}»: coincidencias " + ", ".join(f"«{m}»" for m in matches)
        )
    else:
        reasons.append(
            "categoría «otros»: sin coincidencias; requiere clasificación manual"
        )

    impact, impact_reasons = rules.assess_impact(text, ticket.affected_users, category)
    urgency, urgency_reasons = rules.assess_urgency(text, ticket.workaround_available)
    priority, priority_reasons = rules.compute_priority(impact, urgency, category)
    escalation_level, escalation_reasons = rules.decide_escalation(category, priority)

    reasons += impact_reasons + urgency_reasons + priority_reasons + escalation_reasons

    return TriageResult(
        ticket_id=ticket.id,
        category=category,
        impact=impact,
        urgency=urgency,
        priority=priority,
        escalation_level=escalation_level,
        escalation_team=rules.TEAM_NAMES[escalation_level],
        escalate=escalation_level != rules.LEVEL_1,
        escalate_immediately=priority == Priority.P1,
        needs_manual_review=category == rules.FALLBACK_CATEGORY,
        reasons=reasons,
    )


def triage_all(tickets: Iterable[Ticket]) -> List[TriageResult]:
    return [triage(t) for t in tickets]


def summarize(results: Iterable[TriageResult]) -> Dict[str, Dict[str, int]]:
    """Conteos por categoría, prioridad y nivel de escalación."""
    results = list(results)
    return {
        "total": {"tickets": len(results)},
        "por_categoria": dict(sorted(Counter(r.category for r in results).items())),
        "por_prioridad": dict(sorted(Counter(r.priority.label for r in results).items())),
        "por_escalacion": dict(sorted(Counter(r.escalation_level for r in results).items())),
    }
