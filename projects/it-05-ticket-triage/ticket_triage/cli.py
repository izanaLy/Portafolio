"""Interfaz de línea de comandos.

Uso:
    python -m ticket_triage triage [RUTA] [--format table|json] [--explain]
    python -m ticket_triage summary [RUTA]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from .dataset import DEFAULT_DATASET, load_dataset
from .triage import summarize, triage_all


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ticket_triage",
        description="Simulador de triaje de tickets de soporte (datos sintéticos).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name, help_text in (
        ("triage", "Clasifica y prioriza cada ticket."),
        ("summary", "Muestra conteos por categoría, prioridad y escalación."),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument(
            "path",
            nargs="?",
            default=str(DEFAULT_DATASET),
            help="Archivo JSON de tickets (por defecto: data/synthetic_tickets.json).",
        )
        if name == "triage":
            p.add_argument("--format", choices=("table", "json"), default="table")
            p.add_argument(
                "--explain",
                action="store_true",
                help="En formato tabla, muestra las razones de cada decisión.",
            )
    return parser


def _render_table(results, explain: bool) -> str:
    header = f"{'TICKET':<10} {'CATEGORÍA':<20} {'IMPACTO':<8} {'URGENCIA':<9} {'PRIO':<5} ESCALACIÓN"
    lines = [header, "-" * len(header)]
    for r in results:
        flags = []
        if r.escalate_immediately:
            flags.append("inmediata")
        if r.needs_manual_review:
            flags.append("revisión manual")
        suffix = f" ({', '.join(flags)})" if flags else ""
        lines.append(
            f"{r.ticket_id:<10} {r.category:<20} {r.impact.label:<8} {r.urgency.label:<9} "
            f"{r.priority.label:<5} {r.escalation_level}{suffix}"
        )
        if explain:
            lines.extend(f"    - {reason}" for reason in r.reasons)
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        dataset = load_dataset(Path(args.path))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    results = triage_all(dataset.tickets)

    if args.command == "summary":
        print(json.dumps(summarize(results), ensure_ascii=False, indent=2))
    elif args.format == "json":
        print(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2))
    else:
        print(_render_table(results, args.explain))
    return 0
