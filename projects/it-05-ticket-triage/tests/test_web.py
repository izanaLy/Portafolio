"""HTTP boundary checks for the synthetic local web demo."""
import http.client
import json
import re
import socket
import threading
from functools import partial
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from ticket_triage.web import Handler, ROOT, demo_payload
from ticket_triage.triage import triage
from ticket_triage.models import Ticket


@pytest.fixture
def server():
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), partial(Handler, directory=str(ROOT)))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield 'http://127.0.0.1:' + str(httpd.server_port)
    httpd.shutdown()
    httpd.server_close()
    thread.join()


def post(server, data, origin=None, content_type='application/json'):
    headers = {'Content-Type': content_type}
    if origin:
        headers['Origin'] = origin
    req = Request(server + '/api/triage', json.dumps(data).encode(), headers)
    try:
        response = urlopen(req)
    except HTTPError as error:
        response = error
    return response.status, json.loads(response.read())


def case():
    return {'meta': {'synthetic': True}, 'tickets': [{
        'id': 'LAB-1', 'title': 'Ransomware urgente', 'description': 'Toda la empresa afectada',
        'affected_users': 20, 'workaround_available': True}]}


def test_demo_snapshot_matches_python_engine():
    payload = demo_payload()
    assert payload['synthetic'] is True
    assert len(payload['records']) == 24
    for record in payload['records']:
        assert record['result'] == triage(Ticket.from_dict(record['ticket'])).to_dict()
    snapshot = json.loads((ROOT / 'projects/it-05-ticket-triage/web/demo-data.json').read_text())
    assert snapshot == payload


def test_http_uses_same_engine_and_keeps_security_p1(server):
    status, result = post(server, case(), origin=server)
    assert status == 200
    assert result['result']['priority'] == 'P1'
    assert result['result']['escalation_level'] == 'seguridad'
    assert result['result']['escalate_immediately'] is True
    assert result['result'] == triage(Ticket.from_dict(case()['tickets'][0])).to_dict()


@pytest.mark.parametrize('data', [None, {'meta': None, 'tickets': []},
    {'meta': {'synthetic': False}, 'tickets': []}, {'meta': {'synthetic': True}, 'tickets': [None]},
    {'meta': {'synthetic': True}, 'tickets': []}])
def test_http_rejects_malformed_or_nonsynthetic_data(server, data):
    status, result = post(server, data)
    assert status == 400
    assert result['error']


def test_http_rejects_cross_origin_and_non_json(server):
    assert post(server, case(), origin='https://unrelated.example')[0] == 403
    assert post(server, case(), content_type='text/plain')[0] == 415


@pytest.mark.parametrize('path', ['/.git/config', '/AGENTS.md',
    '/projects/it-05-ticket-triage/web/../ticket_triage/rules.py',
    '/projects/it-05-ticket-triage/web/%2e%2e/ticket_triage/rules.py'])
def test_server_does_not_expose_repository_source(server, path):
    with pytest.raises(HTTPError) as error:
        urlopen(server + path)
    assert error.value.code == 404


def test_pages_and_health_are_available(server):
    for path in ['/', '/portfolio.css', '/projects.json', '/projects/it-05-ticket-triage/web/',
                 '/projects/it-05-ticket-triage/web/app.js', '/api/health', '/api/demo']:
        with urlopen(server + path) as response:
            assert response.status == 200


# --- revisión del PR #3: HEAD, límites, JSON hostil, Host, cuerpo incompleto ----------


def raw(server, method, path, body=None, headers=None):
    """Petición con http.client: permite cabeceras que urllib no deja manipular."""
    host, port = server.removeprefix('http://').split(':')
    conn = http.client.HTTPConnection(host, int(port), timeout=5)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        data = response.read()
        return response.status, dict(response.getheaders()), data
    finally:
        conn.close()


PRIVATE_PATHS = ['/AGENTS.md', '/.git/config', '/INICIAR_DEMO.bat', '/run-demo.py',
                 '/projects/it-05-ticket-triage/ticket_triage/rules.py',
                 '/projects/it-05-ticket-triage/data/synthetic_tickets.json']


@pytest.mark.parametrize('path', PRIVATE_PATHS)
def test_head_does_not_reveal_private_files(server, path):
    # Antes: HEAD respondía 200 con el tamaño del archivo aunque GET diera 404.
    assert raw(server, 'GET', path)[0] == 404
    assert raw(server, 'HEAD', path)[0] == 404


def test_head_on_public_files_still_works(server):
    for path in ['/', '/portfolio.css', '/projects/it-05-ticket-triage/web/app.js']:
        assert raw(server, 'HEAD', path)[0] == 200


def test_markdown_is_served_as_readable_text(server):
    status, headers, _ = raw(server, 'GET', '/projects/it-05-ticket-triage/README.md')
    assert status == 200
    assert headers['Content-type'].startswith('text/plain')  # text/markdown se descarga


def test_deeply_nested_json_is_a_clean_400(server):
    body = b'[' * 16000
    status, _, data = raw(server, 'POST', '/api/triage', body, {'Content-Type': 'application/json'})
    assert status == 400  # antes: RecursionError sin capturar y conexión cortada sin respuesta
    assert 'anidado' in json.loads(data)['error']


@pytest.mark.parametrize('length', ['abc', '-5', '0', ''])
def test_invalid_content_length_is_rejected_without_python_internals(server, length):
    headers = {'Content-Type': 'application/json', 'Content-Length': length}
    status, _, data = raw(server, 'POST', '/api/triage', b'{}', headers)
    assert status in (400, 413)
    assert 'literal' not in json.loads(data)['error']  # antes: «invalid literal for int()»


def test_invalid_json_and_encoding_have_spanish_messages(server):
    head = {'Content-Type': 'application/json'}
    status, _, data = raw(server, 'POST', '/api/triage', b'{no es json', head)
    assert status == 400 and 'JSON inválido' in json.loads(data)['error']
    status, _, data = raw(server, 'POST', '/api/triage', b'\xff\xfe\x00', head)
    assert status == 400 and 'UTF-8' in json.loads(data)['error']


def with_ticket(**fields):
    data = case()
    data['tickets'][0].update(fields)
    return data


@pytest.mark.parametrize('fields', [
    {'title': 'x' * 181}, {'description': 'x' * 3001}, {'affected_users': 1_000_001},
    {'affected_users': 10 ** 30}, {'id': 'L' * 41}])
def test_server_enforces_the_same_limits_as_the_form(server, fields):
    status, result = post(server, with_ticket(**fields))
    assert status == 400  # antes: aceptaba títulos de 5000 caracteres y 10**30 usuarios
    assert result['error']


def test_values_at_the_limits_are_accepted(server):
    fields = {'title': 'x' * 180, 'description': 'y' * 3000, 'affected_users': 1_000_000}
    status, result = post(server, with_ticket(**fields))
    assert status == 200
    assert result['result']['impact'] == 'alto'


@pytest.mark.parametrize('method, path, body', [
    ('GET', '/api/demo', None), ('GET', '/', None), ('HEAD', '/', None),
    ('POST', '/api/triage', json.dumps(case()))])
def test_foreign_host_header_is_rejected(server, method, path, body):
    headers = {'Host': 'evil.example:8001', 'Content-Type': 'application/json'}
    if method == 'POST':
        headers['Origin'] = 'http://evil.example:8001'  # origen "coherente" con el Host falso
    assert raw(server, method, path, body, headers)[0] == 403  # DNS rebinding


def test_localhost_names_are_accepted(server):
    port = server.rsplit(':', 1)[1]
    for host in ('localhost', '127.0.0.1', '[::1]'):
        status, *_ = raw(server, 'GET', '/api/health', headers={'Host': f'{host}:{port}'})
        assert status == 200


def test_bound_non_loopback_address_adds_only_that_host():
    from ticket_triage.web import handler_for, LOOPBACK_HOSTS
    assert handler_for('127.0.0.1').allowed_hosts == LOOPBACK_HOSTS
    assert handler_for('0.0.0.0').allowed_hosts is None  # se pidió explícitamente exponerlo
    assert handler_for('192.168.1.20').allowed_hosts == LOOPBACK_HOSTS | {'192.168.1.20'}


def test_incomplete_body_times_out_instead_of_hanging_a_thread():
    class Quick(Handler):
        timeout = 0.4

    httpd = ThreadingHTTPServer(('127.0.0.1', 0), partial(Quick, directory=str(ROOT)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        sock = socket.create_connection(('127.0.0.1', httpd.server_port), timeout=5)
        sock.sendall(b'POST /api/triage HTTP/1.1\r\nHost: 127.0.0.1\r\n'
                     b'Content-Type: application/json\r\nContent-Length: 100\r\n\r\n{"a":1')
        reply = sock.recv(4096)
        sock.close()
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert reply.startswith(b'HTTP/1.0 408')  # antes: el hilo esperaba para siempre


def test_busy_port_gives_a_friendly_message_not_a_traceback(capsys):
    from ticket_triage.web import main
    blocker = socket.socket()
    blocker.bind(('127.0.0.1', 0))
    blocker.listen(1)
    try:
        assert main(['--port', str(blocker.getsockname()[1])]) == 1
    finally:
        blocker.close()
    err = capsys.readouterr().err
    assert 'No se pudo abrir el puerto' in err and '--port' in err
    assert 'Traceback' not in err


# --- coherencia del lanzador, la documentación y los estilos -------------------------

REPO = ROOT
CSS_FILES = [REPO / 'portfolio.css', REPO / 'projects/it-05-ticket-triage/web/style.css']
DECORATIVE = re.compile(r'\.mock-|\.feature-art|\.hero-art|\.art-caption|\.hero-number|\.floating-label'
                        r'|\.orbit|\.core')


def test_launcher_is_consistent_with_docs_and_code():
    bat = (REPO / 'INICIAR_DEMO.bat').read_bytes()
    text = bat.decode('ascii')
    assert b'\r\n' in bat and b'\n' not in bat.replace(b'\r\n', b'')  # cmd.exe espera CRLF
    assert 'ticket_triage.web' in text and '--open' in text
    assert (REPO / 'projects/it-05-ticket-triage/ticket_triage/web.py').exists()
    assert 'python' in text.lower()  # alternativa cuando no existe el lanzador «py»
    readme = (REPO / 'README.md').read_text(encoding='utf-8')
    assert 'INICIAR_DEMO.bat' in readme and 'run-demo.py' in readme and '8001' in readme


@pytest.mark.parametrize('css', CSS_FILES, ids=lambda p: p.name)
def test_custom_fonts_always_have_a_generic_fallback(css):
    # Sin conexión a Google Fonts, una fuente sin familia genérica cae a Times New Roman.
    for decl in re.findall(r"font:[^;}]*'(?:Space Grotesk|DM Sans)'[^;}]*", css.read_text(encoding='utf-8')):
        assert re.search(r'(sans-serif|system-ui)\s*$', decl), decl


@pytest.mark.parametrize('css', CSS_FILES, ids=lambda p: p.name)
def test_functional_text_is_at_least_11px(css):
    # Excepciones: el arte decorativo del héroe y la maqueta (aria-hidden) y las cabeceras de
    # columna de la bandeja, que pueden bajar a 10 px para caber en columnas de 55-76 px.
    text = css.read_text(encoding='utf-8')
    too_small = []
    for selector, body in re.findall(r'(?<=[{}])([^{}@]+)\{([^{}]*)\}', text):
        if DECORATIVE.search(selector):
            continue
        floor = 10 if selector.strip().startswith('.table-labels') else 11
        for size in re.findall(r'font-size:(\d+(?:\.\d+)?)px|font:(?:\w+ )?(\d+(?:\.\d+)?)px', body):
            value = float(size[0] or size[1])
            if 0 < value < floor:
                too_small.append((selector.strip()[:50], value))
    assert not too_small, too_small


def test_html_pages_declare_an_icon_and_label_icon_only_buttons():
    for page in (REPO / 'index.html', REPO / 'projects/it-05-ticket-triage/web/index.html'):
        assert 'rel="icon"' in page.read_text(encoding='utf-8'), page.name  # evita el 404 de /favicon.ico
    app = (REPO / 'projects/it-05-ticket-triage/web/index.html').read_text(encoding='utf-8')
    for view in ('queue', 'lab'):
        assert re.search(rf'<button[^>]*data-view="{view}"[^>]*title="[^"]+"', app), view  # en móvil solo se ve el icono
