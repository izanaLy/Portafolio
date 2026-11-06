"""Help Desk Portal (software-09): tickets de soporte con triaje del motor IT-05.

Dependencia declarada: el paquete ``ticket_triage`` de ``projects/it-05-ticket-triage``.
Si no está instalado, se añade esa carpeta hermana a ``sys.path`` (sin copiar código).
"""

import sys
from pathlib import Path

try:
    import ticket_triage  # noqa: F401
except ImportError:  # pragma: no cover - depende del entorno
    _engine = Path(__file__).resolve().parents[2] / "it-05-ticket-triage"
    if (_engine / "ticket_triage").is_dir():
        sys.path.insert(0, str(_engine))

from .store import (  # noqa: E402
    STATUSES,
    HelpDesk,
    NotFound,
    ValidationError,
)

__all__ = ["HelpDesk", "NotFound", "STATUSES", "ValidationError"]
