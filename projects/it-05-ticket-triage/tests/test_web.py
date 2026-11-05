"""HTTP boundary checks for the synthetic local web demo."""
import json
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
