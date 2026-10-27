"""The Windows shell must own its caption, without changing game configuration."""
import importlib
import sys
import json
import os
import socket
import subprocess
import time
import urllib.request
from types import SimpleNamespace

import pytest


def module():
    return importlib.import_module('povforge.gui.native_window')


@pytest.mark.parametrize('url', ['https://example.com/', 'http://localhost.evil:8000/',
                                'file:///C:/demo.html', 'http://127.0.0.1:8000/other'])
def test_native_shell_rejects_non_app_urls(url):
    with pytest.raises(ValueError):
        module().create(url)


def test_no_webview_runtime_keeps_browser_fallback(monkeypatch):
    native = module()
    monkeypatch.setattr(native.sys, 'platform', 'win32')
    monkeypatch.setattr(native, 'runtime_available', lambda: False)
    assert native.create('http://127.0.0.1:8765/') is None


def test_closing_native_window_stops_counting_as_a_live_browser(monkeypatch):
    native = module()
    class Event:
        def __iadd__(self, callback):
            self.callback = callback
            return self
    closed = Event()
    window = SimpleNamespace(events=SimpleNamespace(closed=closed), destroy=lambda: closed.callback())
    host = native.NativeWindow(window, SimpleNamespace(), 'unused')
    assert host.pid > 0 and host.poll() is None
    host.close()
    assert host.poll() == 0


@pytest.mark.parametrize('user_closed', [False, True])
def test_failed_async_initialization_requests_fallback_but_user_close_does_not(user_closed):
    native = module()
    class Event:
        def __iadd__(self, callback):
            self.callback = callback
            return self
    closed = Event()
    window = SimpleNamespace(events=SimpleNamespace(closed=closed,
                             loaded=SimpleNamespace(wait=lambda timeout: False)),
                             destroy=lambda: closed.callback())
    # The engine returns from its loop after the host closes the failed window.
    engine = SimpleNamespace(start=lambda ready, **kwargs: ready())
    host = native.NativeWindow(window, engine, 'unused')
    if user_closed:
        host.close()
        host.run()
    else:
        with pytest.raises(RuntimeError, match='initialization'):
            host.run()
    assert host.poll() == 0


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows native integration')
def test_real_native_host_loads_page_and_quits_with_server(tmp_path):
    if not module().runtime_available():
        pytest.skip('WebView2 runtime unavailable')
    pytest.importorskip('webview')
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    script = r'''
import json, sys, time
from http.server import BaseHTTPRequestHandler
from types import SimpleNamespace
from povforge.gui import server, native_window, window_chrome
class App:
    def __init__(self):
        self.references = SimpleNamespace(close=lambda: None)
        self.checker = SimpleNamespace(close=lambda: None)
        self.last_seen = time.time()
        self.bye_at = 0
        self.window = None
    def busy(self): return False
    quit_reason = server.App.quit_reason
def make_handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_GET(self):
            if self.path == '/':
                body = b'<html><title>Native host probe</title><body>Isolated fixture</body></html>'
                ctype = 'text/html'
            elif self.path == '/probe':
                host = app.window
                if not isinstance(host, native_window.NativeWindow) or not host.window.events.loaded.is_set():
                    self.send_error(503); return
                body = json.dumps({'native_type': host.window.native.GetType().FullName,
                    'title': host.window.evaluate_js('document.title'),
                    'dark': window_chrome.apply(host, True),
                    'light': window_chrome.apply(host, False)}).encode()
                ctype = 'application/json'
            elif self.path == '/quit':
                body = b'{}'; ctype = 'application/json'
            else:
                self.send_error(404); return
            self.send_response(200)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)
            if self.path == '/quit': app.quit()
    return Handler
server.App = App
server.make_handler = make_handler
server.main(int(sys.argv[1]))
'''
    env = {**os.environ, 'POVFORGE_STATE': str(tmp_path), 'PYTHONIOENCODING': 'utf-8'}
    with (tmp_path / 'probe.log').open('w', encoding='utf-8') as log:
        proc = subprocess.Popen([sys.executable, '-c', script, str(port)], env=env,
                                stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            result = None
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline and proc.poll() is None:
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/probe', timeout=2) as response:
                        result = json.load(response)
                        break
                except OSError:
                    time.sleep(.2)
            assert result, (tmp_path / 'probe.log').read_text(encoding='utf-8')
            assert result['native_type'] == 'System.Windows.Forms.Form'
            assert result['title'] == 'Native host probe'
            if sys.getwindowsversion().build >= 22000:
                assert result['dark'] and result['light']
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/quit', timeout=3) as response:
                assert response.status == 200
            assert proc.wait(timeout=15) == 0
        finally:
            if proc.poll() is None:
                try:
                    urllib.request.urlopen(f'http://127.0.0.1:{port}/quit', timeout=3).close()
                    proc.wait(timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    proc.terminate()
                    proc.wait(timeout=10)
