"""Reglas explícitas de triaje: categoría, impacto, urgencia, prioridad y escalación.

Todas las reglas son datos y funciones simples, sin aprendizaje automático ni
servicios externos, para que cada decisión pueda explicarse y auditarse.

Convenciones:
* El texto se normaliza a minúsculas y sin acentos antes de buscar coincidencias.
* Una palabra clave coincide como palabra completa (se admite plural simple
  ``s`` / ``es``), por lo que ``red`` no coincide dentro de ``redactar``.
* Las reglas están pensadas para español. Los tickets en otros idiomas
  probablemente terminen como ``otros`` y pidan revisión manual.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable, List, Tuple

from .models import Level, Priority

# ---------------------------------------------------------------------------
# Normalización y búsqueda de coincidencias
# ---------------------------------------------------------------------------


def normalize(text: str) -> str:
    """Minúsculas, sin acentos y con todo lo que no sea alfanumérico como espacio."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()


def _pattern(keyword: str) -> "re.Pattern[str]":
    return re.compile(r"(?<![a-z0-9])" + re.escape(keyword) + r"(?:s|es)?(?![a-z0-9])")


def find_matches(normalized_text: str, keywords: Iterable[str]) -> List[str]:
    """Devuelve las palabras clave presentes (sin repetir, en el orden dado)."""
    return [kw for kw in keywords if _pattern(kw).search(normalized_text)]


# ---------------------------------------------------------------------------
# Categorías
# ---------------------------------------------------------------------------

# En caso de empate de puntaje gana la categoría que aparece primero aquí.
CATEGORY_ORDER: Tuple[str, ...] = (
    "seguridad",
    "infraestructura",
    "red",
    "cuenta_acceso",
    "correo_colaboracion",
    "impresion",
    "hardware",
    "software",
)

FALLBACK_CATEGORY = "otros"

# Peso 5: las señales de seguridad dominan sobre cualquier otra categoría.
# Peso 3: palabra clave fuerte. Peso 2: moderada. Peso 1: débil/genérica.
CATEGORY_KEYWORDS: Dict[str, Dict[str, int]] = {
    "seguridad": {
        "phishing": 5,
        "malware": 5,
        "virus": 5,
        "ransomware": 5,
        "ciberataque": 5,
        "hackeo": 5,
        "suplantacion": 5,
        "acceso no autorizado": 5,
        "cuenta comprometida": 5,
        "correo sospechoso": 5,
        "sospechoso": 5,
        "fuga de datos": 5,
        "datos expuestos": 5,
        "credenciales expuestas": 5,
        "credenciales filtradas": 5,
    },
    "infraestructura": {
        "servidor": 3,
        "base de datos": 3,
        "centro de datos": 3,
        "backup": 3,
        "respaldo": 3,
        "maquina virtual": 3,
        "maquinas virtuales": 3,
        "hipervisor": 3,
        "espacio en disco": 3,
        "cluster": 3,
        "almacenamiento": 2,
        "cpu": 2,
        "monitoreo": 2,
    },
    "red": {
        "vpn": 3,
        "wifi": 3,
        "wi fi": 3,
        "internet": 3,
        "sin conexion": 3,
        "sin red": 3,
        "conectividad": 3,
        "dns": 3,
        "dhcp": 3,
        "latencia": 3,
        "ethernet": 3,
        "router": 3,
        "switch": 3,
        "red": 1,
    },
    "cuenta_acceso": {
        "contrasena": 3,
        "password": 3,
        "cuenta bloqueada": 3,
        "iniciar sesion": 3,
        "inicio de sesion": 3,
        "mfa": 3,
        "doble factor": 3,
        "acceso denegado": 3,
        "alta de usuario": 3,
        "autenticacion": 2,
        "permisos": 2,
        "usuario nuevo": 2,
        "cuenta": 1,
    },
    "correo_colaboracion": {
        "email": 3,
        "outlook": 3,
        "teams": 3,
        "calendario": 3,
        "buzon": 3,
        "videollamada": 3,
        "zoom": 3,
        "correo": 2,
        "reunion": 1,
    },
    "impresion": {
        "impresora": 3,
        "imprimir": 3,
        "imprime": 3,
        "impresion": 3,
        "toner": 3,
        "escaner": 3,
        "atasco": 2,
    },
    "hardware": {
        "laptop": 3,
        "portatil": 3,
        "monitor": 3,
        "teclado": 3,
        "mouse": 3,
        "raton": 3,
        "disco duro": 3,
        "ssd": 3,
        "bateria": 3,
        "no enciende": 3,
        "ventilador": 3,
        "memoria ram": 3,
        "docking": 3,
        "cargador": 3,
        "computadora": 2,
        "pantalla": 2,
        "equipo": 1,
    },
    "software": {
        "instalar": 3,
        "instalacion": 3,
        "excel": 3,
        "word": 3,
        "licencia": 3,
        "navegador": 3,
        "pantalla azul": 3,
        "sistema operativo": 3,
        "aplicacion": 2,
        "programa": 2,
        "actualizacion": 2,
        # Síntomas genéricos: los comparte cualquier aplicación (Teams, Outlook,
        # Excel...), así que pesan menos que el nombre del producto.
        "se cierra": 1,
        "se congela": 1,
        "no abre": 1,
        "error": 1,
    },
}


def classify_category(normalized_text: str) -> Tuple[str, List[str]]:
    """Elige la categoría con mayor puntaje. Devuelve (categoría, coincidencias)."""
    best_category = FALLBACK_CATEGORY
    best_score = 0
    best_matches: List[str] = []
    for category in CATEGORY_ORDER:
        weights = CATEGORY_KEYWORDS[category]
        matches = find_matches(normalized_text, weights)
        score = sum(weights[m] for m in matches)
        if score > best_score:  # '>' mantiene el orden de CATEGORY_ORDER en empates
            best_category, best_score, best_matches = category, score, matches
    return best_category, best_matches


# ---------------------------------------------------------------------------
# Impacto
# ---------------------------------------------------------------------------

USERS_FOR_MEDIUM_IMPACT = 2
USERS_FOR_HIGH_IMPACT = 10

HIGH_IMPACT_KEYWORDS: Tuple[str, ...] = (
    "toda la empresa",
    "toda la oficina",
    "todos los usuarios",
    "todos los empleados",
    "sistema de produccion",
    "ransomware",
    "fuga de datos",
)

MEDIUM_IMPACT_KEYWORDS: Tuple[str, ...] = (
    "departamento",
    "varios usuarios",
    "todo el equipo",
    "sucursal",
    "oficina",
)

# Categorías cuyo impacto mínimo es «medio» (recursos compartidos / riesgo).
CATEGORY_IMPACT_FLOOR: Dict[str, Level] = {
    "infraestructura": Level.MEDIUM,
    "seguridad": Level.MEDIUM,
}


def assess_impact(
    normalized_text: str, affected_users: int, category: str
) -> Tuple[Level, List[str]]:
    """Impacto = máximo entre todas las reglas aplicables. Devuelve (nivel, razones)."""
    candidates: List[Tuple[Level, str]] = [(Level.LOW, "impacto base: bajo")]

    if affected_users >= USERS_FOR_HIGH_IMPACT:
        candidates.append(
            (Level.HIGH, f"{affected_users} usuarios afectados (>= {USERS_FOR_HIGH_IMPACT})")
        )
    elif affected_users >= USERS_FOR_MEDIUM_IMPACT:
        candidates.append(
            (Level.MEDIUM, f"{affected_users} usuarios afectados (>= {USERS_FOR_MEDIUM_IMPACT})")
        )

    for kw in find_matches(normalized_text, HIGH_IMPACT_KEYWORDS):
        candidates.append((Level.HIGH, f"palabra clave de impacto alto: «{kw}»"))
    for kw in find_matches(normalized_text, MEDIUM_IMPACT_KEYWORDS):
        candidates.append((Level.MEDIUM, f"palabra clave de impacto medio: «{kw}»"))

    floor = CATEGORY_IMPACT_FLOOR.get(category)
    if floor is not None:
        candidates.append((floor, f"la categoría «{category}» tiene impacto mínimo {floor.label}"))

    level = max(lvl for lvl, _ in candidates)
    reasons = [reason for lvl, reason in candidates if lvl == level]
    return level, [f"impacto {level.label}: {r}" for r in reasons]


# ---------------------------------------------------------------------------
# Urgencia
# ---------------------------------------------------------------------------

HIGH_URGENCY_KEYWORDS: Tuple[str, ...] = (
    "urgente",
    "critico",
    "no puedo trabajar",
    "no puede trabajar",
    "no pueden trabajar",
    "fuera de servicio",
    "caido",
    "caida",
    "detenido",
    "detenida",
    "sin acceso",
    "ransomware",
    "cliente esperando",
    "clientes esperando",
)

# Frases que bajan la urgencia. Se retiran del texto antes de buscar palabras de
# urgencia alta para que «no es urgente» no cuente como «urgente».
LOW_URGENCY_KEYWORDS: Tuple[str, ...] = (
    "no es urgente",
    "sin prisa",
    "cuando pueda",
    "cuando tengan tiempo",
    "consulta",
    "solicitud",
    "sugerencia",
    "mejora",
    "cosmetico",
)


def assess_urgency(
    normalized_text: str, workaround_available: "bool | None"
) -> Tuple[Level, List[str]]:
    """Urgencia por palabras clave y existencia de alternativa temporal."""
    reasons: List[str] = []

    low_matches = find_matches(normalized_text, LOW_URGENCY_KEYWORDS)
    text_for_high = normalized_text
    for kw in low_matches:
        text_for_high = _pattern(kw).sub(" ", text_for_high)
    high_matches = find_matches(text_for_high, HIGH_URGENCY_KEYWORDS)

    if high_matches:
        level = Level.HIGH
        reasons.append("palabras de urgencia alta: " + ", ".join(f"«{m}»" for m in high_matches))
    elif low_matches:
        level = Level.LOW
        reasons.append("palabras de urgencia baja: " + ", ".join(f"«{m}»" for m in low_matches))
    else:
        level = Level.MEDIUM
        reasons.append("sin palabras de urgencia: urgencia base media")

    if workaround_available is True and level > Level.LOW:
        level = Level(level - 1)
        reasons.append("existe alternativa temporal: la urgencia baja un nivel")
    elif workaround_available is False:
        reasons.append("no existe alternativa temporal (sin cambio de urgencia)")

    return level, [f"urgencia {level.label}: {r}" for r in reasons]


# ---------------------------------------------------------------------------
# Prioridad (matriz impacto x urgencia)
# ---------------------------------------------------------------------------

PRIORITY_MATRIX: Dict[Tuple[Level, Level], Priority] = {
    # (impacto, urgencia): prioridad
    (Level.HIGH, Level.HIGH): Priority.P1,
    (Level.HIGH, Level.MEDIUM): Priority.P2,
    (Level.MEDIUM, Level.HIGH): Priority.P2,
    (Level.HIGH, Level.LOW): Priority.P3,
    (Level.MEDIUM, Level.MEDIUM): Priority.P3,
    (Level.LOW, Level.HIGH): Priority.P3,
    (Level.MEDIUM, Level.LOW): Priority.P4,
    (Level.LOW, Level.MEDIUM): Priority.P4,
    (Level.LOW, Level.LOW): Priority.P4,
}

# Los incidentes de seguridad nunca bajan de esta prioridad.
SECURITY_PRIORITY_FLOOR = Priority.P2


def compute_priority(impact: Level, urgency: Level, category: str) -> Tuple[Priority, List[str]]:
    priority = PRIORITY_MATRIX[(impact, urgency)]
    reasons = [f"matriz impacto {impact.label} x urgencia {urgency.label} -> {priority.label}"]
    if category == "seguridad" and priority > SECURITY_PRIORITY_FLOOR:
        priority = SECURITY_PRIORITY_FLOOR
        reasons.append(
            f"incidente de seguridad: prioridad mínima {SECURITY_PRIORITY_FLOOR.label}"
        )
    return priority, reasons


# ---------------------------------------------------------------------------
# Escalación
# ---------------------------------------------------------------------------

LEVEL_1 = "nivel_1"
LEVEL_2 = "nivel_2"
LEVEL_3 = "nivel_3"
SECURITY = "seguridad"

TEAM_NAMES: Dict[str, str] = {
    LEVEL_1: "Mesa de ayuda (nivel 1)",
    LEVEL_2: "Soporte especializado (nivel 2)",
    LEVEL_3: "Guardia / ingeniería (nivel 3)",
    SECURITY: "Equipo de seguridad",
}


def decide_escalation(category: str, priority: Priority) -> Tuple[str, List[str]]:
    """Devuelve (nivel de escalación, razones). Se aplica la primera regla que coincida."""
    if category == "seguridad":
        return SECURITY, ["categoría «seguridad»: se deriva siempre al equipo de seguridad"]
    if priority == Priority.P1:
        return LEVEL_3, ["prioridad P1: escalación inmediata a nivel 3"]
    if priority == Priority.P2:
        return LEVEL_2, ["prioridad P2: escalación a nivel 2"]
    if category == "infraestructura":
        return LEVEL_2, ["categoría «infraestructura»: nivel 2 como mínimo"]
    return LEVEL_1, ["sin criterios de escalación: se atiende en nivel 1"]
