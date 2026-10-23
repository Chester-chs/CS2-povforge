"""Manual restoration must share the recording startup boundary."""

import io
import threading
from types import SimpleNamespace

import pytest

from povforge import hlae, settings_guard
from povforge.gui import server


def restore_request(job):
    app = SimpleNamespace(job=job, setup=SimpleNamespace(status=lambda: {}))
    handler_type = server.make_handler(app)
    handler = handler_type.__new__(handler_type)
    handler.server = SimpleNamespace(server_address=('127.0.0.1', 49152))
    handler.path = "/api/restore-settings"
    handler.headers = {"Host": "127.0.0.1:49152", "Content-Length": "2", "X-Povforge-Token": handler.csrf_token}
    handler.rfile = io.BytesIO(b"{}")
    result = []
    handler._json = lambda data, code=200: result.append((code, data))
    handler.do_POST()
    return result[0]


@pytest.mark.parametrize("condition", ["recording", "cancelling", "child", "game"])
def test_manual_restore_rejects_active_recording_or_game(monkeypatch, condition):
    job = server.Job()
    if condition == "recording":
        job.state = "running"
    if condition == "cancelling":
        job.cancelling = True
    if condition == "child":
        job.proc = SimpleNamespace(poll=lambda: None)
    monkeypatch.setattr(hlae, "running_processes", lambda: {"cs2.exe"} if condition == "game" else set())
    calls = []
    monkeypatch.setattr(settings_guard, "restore", lambda: calls.append("restore"))
    status, body = restore_request(job)
    assert status == 409
    assert body["error"]
    assert calls == []


def test_manual_restore_works_when_idle(monkeypatch):
    monkeypatch.setattr(hlae, "running_processes", lambda: set())
    calls = []
    monkeypatch.setattr(settings_guard, "restore", lambda: calls.append("restore"))
    assert restore_request(server.Job())[0] == 200
    assert calls == ["restore"]


def test_start_waits_until_manual_restoration_finishes(monkeypatch):
    job = server.Job()
    restoring, release, attempted, launched = [threading.Event() for _ in range(4)]
    monkeypatch.setattr(hlae, "running_processes", lambda: set())

    def restore():
        restoring.set()
        assert release.wait(3)
        return 1

    monkeypatch.setattr(settings_guard, "restore", restore)
    monkeypatch.setattr(job, "_launch", lambda *args: launched.set())
    results = []
    worker = threading.Thread(target=lambda: results.append(restore_request(job)))

    def start():
        attempted.set()
        job.start({"name": "Fixture"}, {})

    starter = threading.Thread(target=start)
    worker.start()
    try:
        assert restoring.wait(3)
        starter.start()
        assert attempted.wait(3)
        assert not launched.wait(0.1)
    finally:
        release.set()
        worker.join(3)
        if starter.ident is not None:
            starter.join(3)
    assert not worker.is_alive() and not starter.is_alive()
    assert results[0][0] == 200 and launched.is_set()
