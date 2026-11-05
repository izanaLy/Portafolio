"""Local, synthetic-data-only web interface. Run: python -m ticket_triage.web."""
from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import webbrowser

from .dataset import load_dataset, parse_dataset
from .triage import triage, summarize

ROOT = Path(__file__).resolve().parents[3]
APP_PATH = "/projects/it-05-ticket-triage/web/"
MAX_BODY = 16384


def demo_payload():
    dataset = load_dataset()
    records = [{"ticket": vars(t), "result": triage(t).to_dict()} for t in dataset.tickets]
    return {"synthetic": True, "records": records,
            "summary": summarize(triage(t) for t in dataset.tickets)}


class Handler(SimpleHTTPRequestHandler):
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

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/health":
            return self.json_response(200, {"ok": True, "synthetic": True})
        if path == "/api/demo":
            return self.json_response(200, demo_payload())
        if path not in ("/", "/index.html", "/portfolio.css", "/projects.json",
                        "/projects/it-05-ticket-triage/README.md") and not path.startswith(APP_PATH):
            return self.send_error(404)
        # Keep the local server from serving source, dotfiles or traversal paths.
        resolved = Path(self.translate_path(self.path)).resolve()
        allowed_root = ROOT / "projects/it-05-ticket-triage/web"
        if path.startswith(APP_PATH) and allowed_root not in resolved.parents and resolved != allowed_root:
            return self.send_error(404)
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/triage":
            return self.json_response(404, {"error": "Ruta no disponible"})
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://{self.headers.get('Host')}",
                                     f"https://{self.headers.get('Host')}"):
            return self.json_response(403, {"error": "Origen no permitido"})
        if self.headers.get_content_type() != "application/json":
            return self.json_response(415, {"error": "Se requiere application/json"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                return self.json_response(413, {"error": "El caso es demasiado extenso"})
            raw = json.loads(self.rfile.read(length).decode("utf-8"))
            dataset = parse_dataset(raw)
            if len(dataset.tickets) != 1:
                raise ValueError("Enviá un único caso ficticio por análisis")
            ticket = dataset.tickets[0]
        except (ValueError, UnicodeError) as exc:
            return self.json_response(400, {"error": str(exc)})
        return self.json_response(200, {"ticket": vars(ticket), "result": triage(ticket).to_dict()})


def main():
    parser = argparse.ArgumentParser(description="Demo web local de IT-05")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8001")))
    parser.add_argument("--host", default="127.0.0.1", help="Dirección de escucha (local por defecto)")
    parser.add_argument("--strictPort", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--open", action="store_true", help="Abrir el navegador")
    args = parser.parse_args()
    with ThreadingHTTPServer((args.host, args.port), partial(Handler, directory=str(ROOT))) as server:
        url = f"http://127.0.0.1:{server.server_port}{APP_PATH}"
        print(f"Triage Studio: {url}\nDatos ficticios. Ctrl+C para cerrar.", flush=True)
        if args.open:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
