"""Tickets ficticios de ejemplo para la demo (no son datos reales)."""

SAMPLES = [
    {"title": "Ransomware en el servidor de archivos",
     "description": "Aparece un mensaje que pide rescate y los archivos compartidos están cifrados. Afecta a todo el departamento.",
     "requester": "usuario-101", "affected_users": 15, "workaround_available": False},
    {"title": "VPN sin conexión",
     "description": "La VPN no conecta desde casa y no puedo acceder a los sistemas internos.",
     "requester": "usuario-102", "affected_users": 3, "workaround_available": None},
    {"title": "Olvidé mi contraseña",
     "description": "No recuerdo mi contraseña y necesito restablecerla para entrar al sistema.",
     "requester": "usuario-103", "affected_users": 1, "workaround_available": None},
    {"title": "Impresora no responde",
     "description": "La impresora del segundo piso no imprime y muestra error de papel.",
     "requester": "usuario-104", "affected_users": 4, "workaround_available": True},
    {"title": "Instalar editor de texto",
     "description": "Necesito instalar un editor de texto en mi equipo para el proyecto.",
     "requester": "usuario-105", "affected_users": 1, "workaround_available": True},
]


def seed_demo(desk) -> None:
    for sample in SAMPLES:
        desk.create_ticket(sample)
