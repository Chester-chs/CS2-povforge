"""Exercise the local HTTP boundary without starting the application or game."""

import http.client
import json
import re
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import quote

import pytest

from povforge.gui.server import make_handler


@pytest.fixture
def http_app(tmp_path):
    output = tmp_path / 'output'
    output.mkdir()
    app = SimpleNamespace(prefs={'output': str(output)}, last_seen=0, bye_at=0)
    server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(app))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    authority = f'127.0.0.1:{server.server_port}'

    def request(path='/', method='GET', headers=None, body=None):
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
        try:
            # Rejection happens before parsing a body. An empty mutation also
            # avoids Windows resetting a closed socket with unread body bytes.
            conn.request(method, path, body=body if body is not None else ('' if method == 'POST' else None), headers=headers or {})
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    yield app, output, authority, request
    server.shutdown()
    server.server_close()
    worker.join(3)


def session_token(request):
    status, html = request()
    assert status == 200
    match = re.search(rb'<meta name="povforge-token" content="([^"]+)"', html)
    assert match, 'page must bootstrap a per-server request token'
    return match[1].decode()


def test_quality_preferences_validate_and_persist(http_app, monkeypatch, tmp_path):
    from povforge.gui import server
    monkeypatch.setenv('POVFORGE_STATE', str(tmp_path / 'state'))
    app, _, authority, request = http_app
    headers = {'Origin': 'http://' + authority, 'X-Povforge-Token': session_token(request)}
    status, payload = request('/api/prefs', 'POST', headers, json.dumps({'record_res': '2160', 'record_fps': 144}))
    assert status == 200
    assert json.loads(payload)['record_fps'] == 144
    assert server.load_prefs()['record_res'] == '2160'
    assert server.load_prefs()['record_fps'] == 144
    for invalid in (0, -1, 241, True, '120', 60.5, None):
        request('/api/prefs', 'POST', headers, json.dumps({'record_fps': invalid}))
        assert app.prefs['record_fps'] == 144


def test_valid_page_thumbnail_and_authenticated_pagehide(http_app):
    app, output, authority, request = http_app
    thumb = output / 'cover.png'
    thumb.write_bytes(b'image')
    assert request('/api/thumb?path=' + quote(str(thumb))) == (200, b'image')
    token = session_token(request)
    assert request('/api/bye', 'POST', {'Origin': 'http://' + authority,
                   'X-Povforge-Token': token})[0] == 200
    assert app.bye_at > 0


@pytest.mark.parametrize('method', ['GET', 'POST'])
def test_attacker_host_and_matching_origin_are_rejected(http_app, method):
    app, _, _, request = http_app
    status, _ = request('/api/bye' if method == 'POST' else '/', method,
                        {'Host': 'attacker.example:1234', 'Origin': 'http://attacker.example:1234'})
    assert status == 403
    assert app.bye_at == 0


@pytest.mark.parametrize('kind', ['missing', 'wrong', 'cross_origin', 'null_origin'])
def test_mutation_requires_token_and_same_origin(http_app, kind):
    app, _, authority, request = http_app
    headers = {'Origin': 'http://' + authority, 'X-Povforge-Token': session_token(request)}
    if kind == 'missing':
        headers.pop('X-Povforge-Token')
    elif kind == 'wrong':
        headers['X-Povforge-Token'] = 'wrong'
    else:
        headers['Origin'] = 'null' if kind == 'null_origin' else 'https://attacker.example'
    assert request('/api/bye', 'POST', headers)[0] == 403
    assert app.bye_at == 0


def test_thumbnail_parent_traversal_is_rejected(http_app):
    _, output, _, request = http_app
    (output.parent / 'private.png').write_bytes(b'private')
    assert request('/api/thumb?path=' + quote(str(output / '..' / 'private.png')))[0] == 404


def test_map_scene_route_and_missing_image(http_app, monkeypatch):
    from povforge import maps
    _, output, _, request = http_app
    scene = output / 'scene.png'
    scene.write_bytes(b'scenery')
    def thumbnail(name):
        if name != 'de_dust2':
            raise ValueError('Unavailable')
        return scene
    monkeypatch.setattr(maps, 'get_map_thumbnail', thumbnail)
    assert request('/api/map-thumbnail?map=de_dust2') == (200, b'scenery')
    assert request('/api/map-thumbnail?map=../secret')[0] == 404
    assert request('/api/map-thumbnail?map=workshop_unknown')[0] == 404


def test_thumbnail_directory_link_cannot_escape_output(http_app):
    _, output, _, request = http_app
    outside = output.parent / 'private'
    outside.mkdir()
    (outside / 'secret.png').write_bytes(b'private')
    link = output / 'linked'
    if sys.platform == 'win32':
        # Fixture paths only. Junction creation does not require developer mode.
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(outside)], check=True, capture_output=True)
    else:
        link.symlink_to(outside, target_is_directory=True)
    try:
        assert request('/api/thumb?path=' + quote(str(link / 'secret.png')))[0] == 404
    finally:
        if sys.platform == 'win32':
            link.rmdir()
        else:
            link.unlink()
