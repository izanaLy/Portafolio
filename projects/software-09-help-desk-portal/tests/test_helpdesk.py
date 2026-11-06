import http.client
import json
import threading

import pytest

from helpdesk import HelpDesk, NotFound, ValidationError
from helpdesk.seed import SAMPLES
from helpdesk.server import make_server
from ticket_triage import Ticket, triage


@pytest.fixture
def desk():
    d = HelpDesk()
    yield d
    d.close()


def ransomware():
    return SAMPLES[0]


# ---- servicio -------------------------------------------------------------
def test_create_uses_it05_engine_decision(desk):
    created = desk.create_ticket(ransomware())
    expected = triage(Ticket.from_dict({**ransomware(), "id": created["id"]}))
    t = created["triage"]
    assert created["id"] == "HD-0001" and created["status"] == "nuevo"
    assert t["priority"] == expected.priority.label == "P1"
    assert t["category"] == expected.category
    assert t["escalation_level"] == expected.escalation_level == "seguridad"
    assert t["reasons"] == expected.reasons and t["reasons"]
    assert created["events"][0]["kind"] == "creado"


def test_ids_are_sequential_and_queue_sorted_by_priority(desk):
    for s in reversed(SAMPLES):
        desk.create_ticket(s)
    ids = [t["id"] for t in desk.list_tickets()]
    assert sorted(ids) == [f"HD-000{i}" for i in range(1, 6)]
    prios = [t["triage"]["priority"] for t in desk.list_tickets()]
    assert prios == sorted(prios)


def test_filters_and_search(desk):
    for s in SAMPLES:
        desk.create_ticket(s)
    assert {t["triage"]["priority"] for t in desk.list_tickets(priority="P1")} == {"P1"}
    assert [t["title"] for t in desk.list_tickets(query="vpn")] == ["VPN sin conexión"]
    assert desk.list_tickets(query="%") == []  # los comodines LIKE se escapan
    assert len(desk.list_tickets(status="nuevo")) == 5 and desk.list_tickets(status="cerrado") == []
    with pytest.raises(ValidationError):
        desk.list_tickets(status="x")
    with pytest.raises(ValidationError):
        desk.list_tickets(priority="P9")


def test_lifecycle_and_history(desk):
    t = desk.create_ticket(SAMPLES[1])["id"]
    desk.change_status(t, {"status": "en_progreso", "assignee": "agente-1"})
    desk.add_comment(t, {"body": "Reiniciando el cliente VPN", "author": "agente-1"})
    desk.change_status(t, {"status": "resuelto"})
    desk.change_status(t, {"status": "en_progreso"})  # reabrir
    desk.change_status(t, {"status": "resuelto"})
    closed = desk.change_status(t, {"status": "cerrado"})
    assert closed["assignee"] == "agente-1"
    assert [e["kind"] for e in closed["events"]] == ["creado", "estado", "comentario", "estado", "estado", "estado", "estado"]
    with pytest.raises(ValidationError, match="cerrado"):
        desk.add_comment(t, {"body": "tarde"})
    with pytest.raises(ValidationError):
        desk.change_status(t, {"status": "nuevo"})


def test_invalid_transitions(desk):
    t = desk.create_ticket(SAMPLES[2])["id"]
    with pytest.raises(ValidationError, match="No se puede pasar"):
        desk.change_status(t, {"status": "cerrado"})
    with pytest.raises(ValidationError):
        desk.change_status(t, {"status": "volando"})


def test_stats(desk):
    for s in SAMPLES:
        desk.create_ticket(s)
    desk.change_status("HD-0001", {"status": "en_progreso"})
    st = desk.stats()
    assert st["total"] == 5 and st["by_status"]["en_progreso"] == 1 and st["by_status"]["nuevo"] == 4
    assert sum(st["by_priority"].values()) == 5


@pytest.mark.parametrize("bad", [
    {}, {"title": "x"}, {"title": " ", "description": "y"}, {"title": "x", "description": 5},
    {"title": "x" * 181, "description": "y"}, {"title": "x", "description": "y" * 3001},
    {"title": "x", "description": "y", "affected_users": 0},
    {"title": "x", "description": "y", "affected_users": True},
    {"title": "x", "description": "y", "affected_users": 10**30},
    {"title": "x", "description": "y", "affected_users": "3"},
    {"title": "x", "description": "y", "workaround_available": "si"},
    [], "texto", None,
])
def test_create_validation(desk, bad):
    with pytest.raises(ValidationError):
        desk.create_ticket(bad)
    assert desk.stats()["total"] == 0


def test_boundary_values_accepted(desk):
    desk.create_ticket({"title": "x" * 180, "description": "y" * 3000, "affected_users": 1_000_000})
    assert desk.stats()["total"] == 1


def test_not_found(desk):
    for call in (lambda: desk.get_ticket("HD-0099"), lambda: desk.add_comment("HD-0099", {"body": "a"}),
                 lambda: desk.change_status("HD-0099", {"status": "en_progreso"})):
        with pytest.raises(NotFound):
            call()


def test_sql_injection_is_inert(desk):
    desk.create_ticket({"title": "x'); DROP TABLE tickets;--", "description": "VPN sin conexión"})
    assert desk.list_tickets(query="' or 1=1 --") == []
    assert desk.stats()["total"] == 1


def test_persistence_in_file(tmp_path):
    path = str(tmp_path / "hd.sqlite")
    a = HelpDesk(path)
    a.create_ticket(SAMPLES[0])
    a.close()
    b = HelpDesk(path)
    assert b.get_ticket("HD-0001")["triage"]["priority"] == "P1"
    assert b.create_ticket(SAMPLES[1])["id"] == "HD-0002"
    b.close()


# ---- HTTP -----------------------------------------------------------------
@pytest.fixture
def server():
    srv = make_server(port=0, seed=False)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv
    srv.shutdown()
    srv.server_close()


def call(srv, method, path, body=None, headers=None, raw=None):
    conn = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=5)
    h = dict(headers or {})
    data = raw if raw is not None else (json.dumps(body) if body is not None else None)
    if data is not None:
        h.setdefault("Content-Type", "application/json")
    conn.request(method, path, body=data, headers=h)
    r = conn.getresponse()
    payload = r.read()
    conn.close()
    try:
        return r.status, json.loads(payload)
    except ValueError:
        return r.status, payload


def test_http_full_flow(server):
    st, t = call(server, "POST", "/api/tickets", ransomware())
    assert st == 201 and t["id"] == "HD-0001" and t["triage"]["priority"] == "P1"
    assert call(server, "GET", "/api/tickets?priority=P1")[1]["tickets"][0]["id"] == "HD-0001"
    assert call(server, "GET", "/api/tickets?q=ransomware")[1]["tickets"]
    assert call(server, "POST", "/api/tickets/HD-0001/comments", {"body": "Aislado de la red"})[0] == 200
    st, t = call(server, "POST", "/api/tickets/HD-0001/status", {"status": "en_progreso"})
    assert st == 200 and t["status"] == "en_progreso"
    assert call(server, "GET", "/api/stats")[1]["total"] == 1
    assert call(server, "GET", "/api/tickets/HD-0001")[1]["events"][-1]["kind"] == "estado"


def test_http_errors(server):
    assert call(server, "POST", "/api/tickets", {"title": ""})[0] == 400
    assert call(server, "POST", "/api/tickets/HD-0001/status", {"status": "en_progreso"})[0] == 404
    assert call(server, "GET", "/api/tickets/..%2fsecret")[0] == 404
    assert call(server, "GET", "/api/tickets?status=x")[0] == 400
    assert call(server, "GET", "/nada")[0] == 404
    assert call(server, "POST", "/api/tickets", raw="{no")[0] == 400
    assert call(server, "POST", "/api/tickets", raw=b"\xff\xfe".decode("latin-1"))[0] == 400
    assert call(server, "POST", "/api/tickets", raw="[" * 8000)[0] == 400
    assert call(server, "POST", "/api/tickets", raw=" " * 20000)[0] == 413
    assert call(server, "POST", "/api/tickets", headers={"Content-Length": "abc"})[0] == 400


def test_http_host_and_origin(server):
    assert call(server, "GET", "/api/stats", headers={"Host": "evil.example"})[0] == 403
    assert call(server, "POST", "/api/tickets", ransomware(), headers={"Origin": "http://evil.example"})[0] == 403
    assert call(server, "POST", "/api/tickets", ransomware(), headers={"Origin": "http://localhost:8002"})[0] == 201


def test_http_static_is_closed_list_and_head_parity(server):
    for path in ("/", "/app.js"):
        assert call(server, "GET", path)[0] == 200 and call(server, "HEAD", path)[0] == 200
    for path in ("/helpdesk/store.py", "/README.md", "/.git/config", "/../AGENTS.md", "/tests/test_helpdesk.py"):
        assert call(server, "GET", path)[0] == 404 and call(server, "HEAD", path)[0] == 404


def test_page_has_no_innerhtml():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "web"
    for name in ("app.js", "index.html"):
        text = (root / name).read_text(encoding="utf-8")
        assert "innerHTML" not in text and "outerHTML" not in text and "document.write" not in text
