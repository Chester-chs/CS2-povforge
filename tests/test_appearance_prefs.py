import json
import http.client as client
import re
import threading
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from povforge.gui import server


def test_appearance_preferences_survive_restart_and_reject_invalid_values(tmp_path, monkeypatch):
    monkeypatch.setenv('POVFORGE_STATE', str(tmp_path))
    prefs = server.load_prefs()
    server.update_appearance(prefs, {'appearance': 'dark', 'accent': 'purple', 'font': 'yahei', 'popup_radius': 22})
    server.save_prefs(prefs)
    loaded = server.load_prefs()
    assert (loaded['appearance'], loaded['accent'], loaded['font'], loaded['popup_radius']) == ('dark', 'purple', 'yahei', 22)
    server.update_appearance(loaded, {'font': 'arbitrary;css', 'popup_radius': -7})
    assert loaded['font'] == 'yahei'
    assert loaded['popup_radius'] == 22
    saved = server.app_dir() / 'app.json'
    saved.write_text(json.dumps({'font': ['invalid'], 'popup_radius': 'broken'}))
    loaded = server.load_prefs()
    assert loaded['font'] == 'system'
    assert loaded['popup_radius'] == 14


def test_http_preferences_and_window_theme_are_validated(tmp_path, monkeypatch):
    monkeypatch.setenv('POVFORGE_STATE', str(tmp_path))
    from povforge.gui import window_chrome
    window = object()
    calls = []
    monkeypatch.setattr(window_chrome, 'apply', lambda process, dark: calls.append((process, dark)) or True)
    app = SimpleNamespace(prefs=server.load_prefs(), last_seen=0, window=window)
    http = ThreadingHTTPServer(('127.0.0.1', 0), server.make_handler(app))
    worker = threading.Thread(target=http.serve_forever, daemon=True)
    worker.start()
    # Use the normal token bootstrapped into the frontend, not a test bypass.
    connection = client.HTTPConnection('127.0.0.1', http.server_port, timeout=3)
    try:
        connection.request('GET', '/')
        token = re.search(rb'name="povforge-token" content="([^"]+)"', connection.getresponse().read())[1].decode()

        def post(path, data):
            connection.request('POST', path, json.dumps(data), {'Content-Type': 'application/json', 'X-Povforge-Token': token})
            response = connection.getresponse()
            return response.status, json.loads(response.read())

        status, data = post('/api/prefs', {'font': 'simsun', 'popup_radius': 28, 'appearance': 'dark'})
        assert status == 200 and data['font'] == 'simsun' and data['popup_radius'] == 28
        assert server.load_prefs()['font'] == 'simsun'
        assert post('/api/window-theme', {'dark': 'yes'})[0] == 400
        assert calls == []
        assert post('/api/window-theme', {'dark': True}) == (200, {'applied': True})
        assert calls == [(window, True)]
    finally:
        connection.close()
        http.shutdown()
        http.server_close()
        worker.join(3)
