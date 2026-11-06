"""Servidor HTTP local (biblioteca estándar) para el Help Desk Portal.

Solo escucha en esta computadora por defecto, valida la cabecera Host y el Origin,
limita el cuerpo y sirve una lista cerrada de archivos estáticos.
"""

from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlsplit

from .store import HelpDesk, NotFound, ValidationError

WEB = Path(__file__).resolve().parents[1] / "web"
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/index.html": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8")}
MAX_BODY = 16384
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}
ID_RE = re.compile(r"^HD-\d{4,}$")


def _host_only(value: str) -> str:
    value = value.strip().lower()
    if value.startswith("["):
        return value.split("]")[0] + "]"
    return value.split(":")[0]


class Handler(BaseHTTPRequestHandler):
    desk: HelpDesk
    allowed_hosts = LOCAL_HOSTS
    timeout = 10
    server_version = "HelpDesk/1.0"

    def log_message(self, *args: Any) -> None:  # silencioso
        pass

    # ---- utilidades ---------------------------------------------------
    def _send(self, status: int, payload: Any, ctype: str = "application/json; charset=utf-8", head: bool = False) -> None:
        body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def _error(self, status: int, message: str, head: bool = False) -> None:
        self._send(status, {"error": message}, head=head)

    def _host_ok(self) -> bool:
        return _host_only(self.headers.get("Host", "")) in self.allowed_hosts

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        return origin is None or _host_only(urlsplit(origin).netloc) in self.allowed_hosts

    # ---- métodos ------------------------------------------------------
    def do_HEAD(self) -> None:
        self._get(head=True)

    def do_GET(self) -> None:
        self._get(head=False)

    def _get(self, head: bool) -> None:
        if not self._host_ok():
            return self._error(403, "Host no permitido.", head)
        url = urlsplit(self.path)
        if url.path in STATIC:
            name, ctype = STATIC[url.path]
            return self._send(200, (WEB / name).read_bytes(), ctype, head)
        try:
            if url.path == "/api/tickets":
                q = parse_qs(url.query)
                first = lambda k: (q.get(k) or [None])[0]  # noqa: E731
                return self._send(200, {"tickets": self.desk.list_tickets(first("status"), first("priority"), first("q"))}, head=head)
            if url.path == "/api/stats":
                return self._send(200, self.desk.stats(), head=head)
            m = re.fullmatch(r"/api/tickets/([^/]+)", url.path)
            if m and ID_RE.match(m.group(1)):
                return self._send(200, self.desk.get_ticket(m.group(1)), head=head)
        except ValidationError as exc:
            return self._error(400, str(exc), head)
        except NotFound as exc:
            return self._error(404, str(exc), head)
        self._error(404, "No encontrado.", head)

    def do_POST(self) -> None:
        if not self._host_ok():
            return self._error(403, "Host no permitido.")
        if not self._origin_ok():
            return self._error(403, "Origen no permitido.")
        url = urlsplit(self.path)
        try:
            length_raw = self.headers.get("Content-Length", "")
            if not length_raw.isdigit():
                return self._error(400, "Falta una longitud de cuerpo válida.")
            length = int(length_raw)
            if length > MAX_BODY:
                return self._error(413, "El cuerpo supera 16 KiB.")
            try:
                raw = self.rfile.read(length)
            except TimeoutError:
                return self._error(408, "Tiempo de espera agotado.")
            if len(raw) < length:
                return self._error(400, "Cuerpo incompleto.")
            try:
                data = json.loads(raw.decode("utf-8"))
            except UnicodeDecodeError:
                return self._error(400, "El cuerpo debe ser UTF-8.")
            except json.JSONDecodeError as exc:
                return self._error(400, f"JSON inválido (línea {exc.lineno}, columna {exc.colno}).")
            except RecursionError:
                return self._error(400, "El JSON está demasiado anidado.")

            if url.path == "/api/tickets":
                return self._send(201, self.desk.create_ticket(data))
            m = re.fullmatch(r"/api/tickets/([^/]+)/(comments|status)", url.path)
            if m and ID_RE.match(m.group(1)):
                action = self.desk.add_comment if m.group(2) == "comments" else self.desk.change_status
                return self._send(200, action(m.group(1), data))
            self._error(404, "No encontrado.")
        except ValidationError as exc:
            self._error(400, str(exc))
        except NotFound as exc:
            self._error(404, str(exc))
        except Exception:  # noqa: BLE001 - sin trazas hacia el cliente
            self._error(500, "Error interno.")


def make_server(host: str = "127.0.0.1", port: int = 8002, db: str = ":memory:", seed: bool = False) -> ThreadingHTTPServer:
    desk = HelpDesk(db)
    if seed:
        from .seed import seed_demo
        seed_demo(desk)
    allowed = set(LOCAL_HOSTS)
    if host not in ("0.0.0.0", "::", "") and host not in allowed:
        allowed.add(host.lower())
    handler = type("BoundHandler", (Handler,), {"desk": desk, "allowed_hosts": allowed})
    return ThreadingHTTPServer((host, port), handler)


def main(argv: Optional[list] = None) -> int:
    p = argparse.ArgumentParser(description="Help Desk Portal (datos ficticios, solo local).")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8002)
    p.add_argument("--db", default=":memory:", help="Archivo SQLite (por defecto, memoria).")
    p.add_argument("--seed", action="store_true", help="Cargar 5 tickets ficticios de ejemplo.")
    args = p.parse_args(argv)
    try:
        server = make_server(args.host, args.port, args.db, args.seed)
    except OSError as exc:
        print(f"No se pudo abrir {args.host}:{args.port}: {exc.strerror}. Probá con --port {args.port + 1}.")
        return 1
    print(f"Help Desk Portal en http://{args.host}:{args.port}/  (Ctrl+C para cerrar)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
