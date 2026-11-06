"""Almacén SQLite y reglas del flujo de tickets.

El triaje lo decide siempre ``ticket_triage.triage`` (IT-05); aquí solo se guarda
su resultado y se gestiona el ciclo de vida. Sin autenticación: es una demo local
con datos ficticios.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ticket_triage import Ticket, triage

STATUSES = ("nuevo", "en_progreso", "resuelto", "cerrado")
TRANSITIONS = {
    "nuevo": ("en_progreso", "resuelto"),
    "en_progreso": ("resuelto",),
    "resuelto": ("en_progreso", "cerrado"),  # reabrir o cerrar
    "cerrado": (),
}
MAX_TITLE, MAX_DESCRIPTION, MAX_COMMENT = 180, 3000, 1000
MAX_AUTHOR, MAX_USERS, MAX_QUERY = 60, 1_000_000, 100

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
  id TEXT PRIMARY KEY, seq INTEGER UNIQUE NOT NULL,
  title TEXT NOT NULL, description TEXT NOT NULL, requester TEXT NOT NULL,
  affected_users INTEGER NOT NULL, workaround TEXT NOT NULL,
  status TEXT NOT NULL, assignee TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  category TEXT NOT NULL, impact TEXT NOT NULL, urgency TEXT NOT NULL,
  priority INTEGER NOT NULL, escalation_level TEXT NOT NULL,
  escalation_team TEXT NOT NULL, escalate_immediately INTEGER NOT NULL,
  needs_manual_review INTEGER NOT NULL, reasons TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ticket_id TEXT NOT NULL REFERENCES tickets(id),
  at TEXT NOT NULL, kind TEXT NOT NULL, author TEXT NOT NULL, body TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_ticket ON events(ticket_id);
"""


class ValidationError(ValueError):
    """Entrada inválida (se traduce a HTTP 400)."""


class NotFound(LookupError):
    """Ticket inexistente (se traduce a HTTP 404)."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(data: Dict[str, Any], key: str, limit: int, label: str, required: bool = True) -> str:
    value = data.get(key)
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise ValidationError(f"{label} debe ser texto.")
    value = value.strip()
    if required and not value:
        raise ValidationError(f"{label} es obligatorio.")
    if len(value) > limit:
        raise ValidationError(f"{label} admite como máximo {limit} caracteres.")
    return value


class HelpDesk:
    """Servicio de tickets. ``path=":memory:"`` por defecto; seguro entre hilos."""

    def __init__(self, path: str = ":memory:") -> None:
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(SCHEMA)
            self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # ---- creación -------------------------------------------------------
    def create_ticket(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("El cuerpo debe ser un objeto JSON.")
        title = _text(data, "title", MAX_TITLE, "El título")
        description = _text(data, "description", MAX_DESCRIPTION, "La descripción")
        requester = _text(data, "requester", MAX_AUTHOR, "El solicitante", required=False) or "usuario-demo"
        users = data.get("affected_users", 1)
        if isinstance(users, bool) or not isinstance(users, int) or not 1 <= users <= MAX_USERS:
            raise ValidationError(f"Las personas afectadas deben ser un entero entre 1 y {MAX_USERS}.")
        workaround = data.get("workaround_available")
        if workaround is not None and not isinstance(workaround, bool):
            raise ValidationError("La alternativa temporal debe ser true, false o null.")

        with self._lock:
            seq = (self._db.execute("SELECT COALESCE(MAX(seq),0)+1 FROM tickets").fetchone()[0])
            ticket_id = f"HD-{seq:04d}"
            try:
                result = triage(Ticket.from_dict({
                    "id": ticket_id, "title": title, "description": description,
                    "requester": requester, "affected_users": users,
                    "workaround_available": workaround,
                }))
            except ValueError as exc:  # el motor mantiene su propia validación
                raise ValidationError(str(exc)) from None
            now = _now()
            self._db.execute(
                "INSERT INTO tickets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (ticket_id, seq, title, description, requester, users,
                 {True: "yes", False: "no", None: "unknown"}[workaround],
                 "nuevo", None, now, now, result.category, result.impact.label,
                 result.urgency.label, int(result.priority), result.escalation_level,
                 result.escalation_team, int(result.escalate_immediately),
                 int(result.needs_manual_review), json.dumps(result.reasons, ensure_ascii=False)),
            )
            self._event(ticket_id, "creado", requester, f"Ticket creado con prioridad {result.priority.label}.")
            self._db.commit()
            return self.get_ticket(ticket_id)

    # ---- consulta -------------------------------------------------------
    def get_ticket(self, ticket_id: str) -> Dict[str, Any]:
        with self._lock:
            row = self._db.execute("SELECT * FROM tickets WHERE id=?", (ticket_id,)).fetchone()
            if row is None:
                raise NotFound(f"No existe el ticket {ticket_id}.")
            ticket = self._ticket(row)
            ticket["events"] = [dict(e) for e in self._db.execute(
                "SELECT at, kind, author, body FROM events WHERE ticket_id=? ORDER BY id", (ticket_id,))]
            return ticket

    def list_tickets(self, status: Optional[str] = None, priority: Optional[str] = None,
                     query: Optional[str] = None) -> List[Dict[str, Any]]:
        where, args = [], []
        if status:
            if status not in STATUSES:
                raise ValidationError(f"Estado desconocido: {status!r}.")
            where.append("status=?"); args.append(status)
        if priority:
            if priority not in ("P1", "P2", "P3", "P4"):
                raise ValidationError(f"Prioridad desconocida: {priority!r}.")
            where.append("priority=?"); args.append(int(priority[1]))
        if query:
            if len(query) > MAX_QUERY:
                raise ValidationError(f"La búsqueda admite como máximo {MAX_QUERY} caracteres.")
            like = "%" + query.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            where.append("(LOWER(title) LIKE ? ESCAPE '\\' OR LOWER(id) LIKE ? ESCAPE '\\' OR LOWER(category) LIKE ? ESCAPE '\\')")
            args += [like, like, like]
        sql = "SELECT * FROM tickets" + (" WHERE " + " AND ".join(where) if where else "")
        sql += " ORDER BY priority, seq"
        with self._lock:
            return [self._ticket(r) for r in self._db.execute(sql, args)]

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            by_status = {s: 0 for s in STATUSES}
            by_priority = {f"P{i}": 0 for i in range(1, 5)}
            for r in self._db.execute("SELECT status, priority, COUNT(*) n FROM tickets GROUP BY status, priority"):
                by_status[r["status"]] += r["n"]
                by_priority[f"P{r['priority']}"] += r["n"]
            return {"total": sum(by_status.values()), "by_status": by_status, "by_priority": by_priority}

    # ---- cambios --------------------------------------------------------
    def add_comment(self, ticket_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("El cuerpo debe ser un objeto JSON.")
        body = _text(data, "body", MAX_COMMENT, "El comentario")
        author = _text(data, "author", MAX_AUTHOR, "El autor", required=False) or "usuario-demo"
        with self._lock:
            self.get_ticket(ticket_id)
            if self._db.execute("SELECT status FROM tickets WHERE id=?", (ticket_id,)).fetchone()[0] == "cerrado":
                raise ValidationError("El ticket está cerrado y no admite comentarios.")
            self._event(ticket_id, "comentario", author, body)
            self._touch(ticket_id)
            self._db.commit()
            return self.get_ticket(ticket_id)

    def change_status(self, ticket_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            raise ValidationError("El cuerpo debe ser un objeto JSON.")
        new = data.get("status")
        if new not in STATUSES:
            raise ValidationError(f"Estado desconocido: {new!r}. Opciones: {', '.join(STATUSES)}.")
        author = _text(data, "author", MAX_AUTHOR, "El autor", required=False) or "agente-demo"
        assignee = _text(data, "assignee", MAX_AUTHOR, "El responsable", required=False)
        with self._lock:
            current = self.get_ticket(ticket_id)["status"]
            if new not in TRANSITIONS[current]:
                allowed = ", ".join(TRANSITIONS[current]) or "ninguno"
                raise ValidationError(f"No se puede pasar de {current} a {new}. Permitidos: {allowed}.")
            if assignee:
                self._db.execute("UPDATE tickets SET assignee=? WHERE id=?", (assignee, ticket_id))
            self._db.execute("UPDATE tickets SET status=? WHERE id=?", (new, ticket_id))
            self._event(ticket_id, "estado", author, f"{current} → {new}" + (f" (responsable: {assignee})" if assignee else ""))
            self._touch(ticket_id)
            self._db.commit()
            return self.get_ticket(ticket_id)

    # ---- internos -------------------------------------------------------
    def _event(self, ticket_id: str, kind: str, author: str, body: str) -> None:
        self._db.execute("INSERT INTO events (ticket_id, at, kind, author, body) VALUES (?,?,?,?,?)",
                         (ticket_id, _now(), kind, author, body))

    def _touch(self, ticket_id: str) -> None:
        self._db.execute("UPDATE tickets SET updated_at=? WHERE id=?", (_now(), ticket_id))

    @staticmethod
    def _ticket(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"], "title": row["title"], "description": row["description"],
            "requester": row["requester"], "affected_users": row["affected_users"],
            "workaround_available": {"yes": True, "no": False, "unknown": None}[row["workaround"]],
            "status": row["status"], "assignee": row["assignee"],
            "created_at": row["created_at"], "updated_at": row["updated_at"],
            "triage": {
                "category": row["category"], "impact": row["impact"], "urgency": row["urgency"],
                "priority": f"P{row['priority']}", "escalation_level": row["escalation_level"],
                "escalation_team": row["escalation_team"],
                "escalate_immediately": bool(row["escalate_immediately"]),
                "needs_manual_review": bool(row["needs_manual_review"]),
                "reasons": json.loads(row["reasons"]),
            },
        }
