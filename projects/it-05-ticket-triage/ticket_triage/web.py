"""Local, synthetic-data-only web interface. Run: python -m ticket_triage.web."""
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit
import webbrowser

from .dataset import load_dataset, parse_dataset
from .triage import triage, summarize

ROOT = Path(__file__).resolve().parents[3]
APP_PATH = "/projects/it-05-ticket-triage/web/"
APP_ROOT = ROOT / "projects/it-05-ticket-triage/web"
STATIC_FILES = ("/", "/index.html", "/portfolio.css", "/projects.json",
                "/projects/it-05-ticket-triage/README.md")
MAX_BODY = 16384
# Límites que ya aplica el formulario (maxlength, min, max). El servidor no confía en el navegador.
MAX_ID = 40
MAX_TITLE = 180
MAX_DESCRIPTION = 3000
MAX_AFFECTED_USERS = 1_000_000
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
WILDCARD_HOSTS = ("", "0.0.0.0", "::")


def demo_payload():
    dataset = load_dataset()
    records = [{"ticket": vars(t), "result": triage(t).to_dict()} for t in dataset.tickets]
    return {"synthetic": True, "records": records,
            "summary": summarize(triage(t) for t in dataset.tickets)}


def check_limits(ticket):
    """Mismos límites que el formulario; lanza ValueError con un mensaje en español."""
    if len(ticket.id) > MAX_ID:
        raise ValueError(f"El identificador admite hasta {MAX_ID} caracteres")
    if len(ticket.title) > MAX_TITLE:
        raise ValueError(f"El título admite hasta {MAX_TITLE} caracteres")
    if len(ticket.description) > MAX_DESCRIPTION:
        raise ValueError(f"La descripción admite hasta {MAX_DESCRIPTION} caracteres")
    if ticket.affected_users > MAX_AFFECTED_USERS:
        raise ValueError(f"Las personas afectadas no pueden superar {MAX_AFFECTED_USERS}")


class Handler(SimpleHTTPRequestHandler):
    timeout = 10  # segundos: un cuerpo incompleto no deja un hilo esperando para siempre
    # Nombres de host aceptados en la cabecera Host (protege contra DNS rebinding).
    # None desactiva la comprobación; solo se usa si se pide escuchar en todas las interfaces.
    allowed_hosts = LOOPBACK_HOSTS
    # Los navegadores descargan text/markdown; como texto plano el README se puede leer en pantalla.
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".md": "text/plain; charset=utf-8"}

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def json_response(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def host_allowed(self):
        if self.allowed_hosts is None:
            return True
        try:
            hostname = urlsplit("//" + (self.headers.get("Host") or "")).hostname
        except ValueError:
            return False
        return hostname in self.allowed_hosts

    def reject_host(self):
        """Responde 403 y devuelve True si la cabecera Host no es de esta computadora."""
        if self.host_allowed():
            return False
        self.json_response(403, {"error": "Host no permitido"})
        return True

    def request_path(self):
        return self.path.split("?", 1)[0].split("#", 1)[0]

    def static_allowed(self, path):
        """Lista cerrada de archivos públicos; nada de código fuente, dotfiles ni recorridos de ruta."""
        if path in STATIC_FILES:
            return True
        if not path.startswith(APP_PATH):
            return False
        resolved = Path(self.translate_path(self.path)).resolve()
        return resolved == APP_ROOT or APP_ROOT in resolved.parents

    def do_GET(self):
        if self.reject_host():
            return
        path = self.request_path()
        if path == "/api/health":
            return self.json_response(200, {"ok": True, "synthetic": True})
        if path == "/api/demo":
            return self.json_response(200, demo_payload())
        if not self.static_allowed(path):
            return self.send_error(404)
        return super().do_GET()

    def do_HEAD(self):
        # HEAD aplica las mismas reglas que GET: no debe revelar si existe ni cuánto pesa un archivo privado.
        if self.reject_host():
            return
        path = self.request_path()
        if path.startswith("/api/") or not self.static_allowed(path):
            return self.send_error(404)
        return super().do_HEAD()

    def do_POST(self):
        if self.reject_host():
            return
        if self.request_path() != "/api/triage":
            return self.json_response(404, {"error": "Ruta no disponible"})
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://{self.headers.get('Host')}",
                                     f"https://{self.headers.get('Host')}"):
            return self.json_response(403, {"error": "Origen no permitido"})
        if self.headers.get_content_type() != "application/json":
            return self.json_response(415, {"error": "Se requiere application/json"})
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self.json_response(400, {"error": "Falta una longitud de contenido válida"})
        if length <= 0:
            return self.json_response(400, {"error": "El cuerpo de la solicitud está vacío"})
        if length > MAX_BODY:
            return self.json_response(413, {"error": "El caso es demasiado extenso"})
        try:
            body = self.rfile.read(length)
        except TimeoutError:
            self.close_connection = True
            return self.json_response(408, {"error": "La solicitud tardó demasiado en llegar"})
        if len(body) != length:
            return self.json_response(400, {"error": "El cuerpo de la solicitud llegó incompleto"})
        try:
            dataset = parse_dataset(json.loads(body.decode("utf-8")))
            if len(dataset.tickets) != 1:
                raise ValueError("Enviá un único caso ficticio por análisis")
            ticket = dataset.tickets[0]
            check_limits(ticket)
        except UnicodeError:
            return self.json_response(400, {"error": "El cuerpo debe estar codificado en UTF-8"})
        except json.JSONDecodeError as exc:
            return self.json_response(400, {"error": f"JSON inválido (línea {exc.lineno}, columna {exc.colno})"})
        except RecursionError:
            return self.json_response(400, {"error": "El JSON está demasiado anidado"})
        except ValueError as exc:
            return self.json_response(400, {"error": str(exc)})
        try:
            payload = {"ticket": vars(ticket), "result": triage(ticket).to_dict()}
        except Exception as exc:  # noqa: BLE001 - nunca exponer trazas al navegador
            self.log_error("Error al analizar el caso: %r", exc)
            return self.json_response(500, {"error": "No se pudo analizar el caso"})
        return self.json_response(200, payload)


def handler_for(host):
    """Handler con la lista de hosts permitidos acorde con la dirección de escucha."""
    host = host.lower()
    if host in WILDCARD_HOSTS:
        return type("OpenHandler", (Handler,), {"allowed_hosts": None})
    if host in LOOPBACK_HOSTS:
        return Handler
    return type("BoundHandler", (Handler,), {"allowed_hosts": LOOPBACK_HOSTS | {host}})


def main(argv=None):
    parser = argparse.ArgumentParser(description="Demo web local de IT-05")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8001")))
    parser.add_argument("--host", default="127.0.0.1", help="Dirección de escucha (local por defecto)")
    parser.add_argument("--strictPort", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--open", action="store_true", help="Abrir el navegador")
    args = parser.parse_args(argv)
    try:
        server = ThreadingHTTPServer((args.host, args.port),
                                     partial(handler_for(args.host), directory=str(ROOT)))
    except OSError as exc:
        print(f"No se pudo abrir el puerto {args.port}: {exc.strerror or exc}.\n"
              f"Probá con otro: py run-demo.py --port {args.port + 1} --open", file=sys.stderr)
        return 1
    with server:
        url = f"http://127.0.0.1:{server.server_port}{APP_PATH}"
        print(f"Triage Studio: {url}\nDatos ficticios. Ctrl+C para cerrar.", flush=True)
        if args.host.lower() in WILDCARD_HOSTS:
            print("Atención: escuchando en todas las interfaces; otros equipos de la red podrán abrir la demo.",
                  flush=True)
        if args.open:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
