"""Job failures must leave the GUI and queue recoverable."""

import pytest
from types import SimpleNamespace

from povforge import hlae, settings_guard
from povforge.gui import server


@pytest.mark.parametrize("boundary", ["config", "launch"])
def test_start_failure_does_not_leave_job_running(tmp_path, monkeypatch, boundary):
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path / "state"))
    prefs = server.load_prefs()
    prefs.update(output=str(tmp_path / "videos"), by_player=False)

    def fail(*args, **kwargs):
        raise OSError(f"{boundary} failed")

    monkeypatch.setattr(server if boundary == "config" else server.subprocess,
                        "write_job_config" if boundary == "config" else "Popen", fail)
    job = server.Job()
    queue = server.Queue(job, prefs)
    queue.add("fixture.dem", "111", "Player", [], "")
    assert job.snapshot()["state"] == "error"
    assert f"{boundary} failed" in job.snapshot()["error"]
    assert queue.snapshot()["items"][0]["state"] == "error"
    queue.retry(1)
    assert job.snapshot()["state"] == "error"
    assert "already running" not in queue.snapshot()["items"][0]["error"].lower()


def test_queue_reserves_one_start_while_child_is_being_prepared(monkeypatch):
    job = server.Job()
    queue = server.Queue(job, {})
    queue.items = [{"id": 1, "name": "first", "state": "queued"},
                   {"id": 2, "name": "second", "state": "queued"}]
    calls = []

    def start(item, prefs):
        calls.append(item["id"])
        if len(calls) == 1:
            queue._start_next()  # Another request arrives while start prepares files.
        job.state = "running"

    monkeypatch.setattr(job, "start", start)
    queue._start_next()
    assert calls == [1]
    assert [i["state"] for i in queue.snapshot()["items"]] == ["running", "queued"]


def test_cancel_notifies_queue_once_after_settings_cleanup(monkeypatch):
    events = []
    job = server.Job()
    job.state = "running"
    job.proc = SimpleNamespace(pid=12345, stdout=iter([]), wait=lambda: 1, poll=lambda: 1)
    job.on_finish = lambda: events.append("notify")
    monkeypatch.setattr(server.sys, "platform", "win32")
    monkeypatch.setattr(hlae, "running_processes", lambda: set())
    monkeypatch.setattr(settings_guard, "owned_by", lambda _: True)
    monkeypatch.setattr(settings_guard, "pending", lambda: False)

    def stop(args, **kwargs):
        if "/pid" in args:
            events.append("child-exit")
            job._read()  # Reader wakes as soon as taskkill ends the child.
        return SimpleNamespace(returncode=0)

    def restore():
        assert job.busy
        events.append("restore")
        return 0

    monkeypatch.setattr(server.subprocess, "run", stop)
    monkeypatch.setattr(settings_guard, "restore", restore)
    job.cancel()
    assert events == ["child-exit", "restore", "notify"]
    assert job.snapshot()["state"] == "cancelled"


def test_old_reader_cannot_change_a_new_jobs_result_or_error():
    job = server.Job()
    new = SimpleNamespace(poll=lambda: None)

    class LateOutput:
        def __iter__(self):
            job.proc = new  # Cancellation/restart happened while the read blocked.
            job.state, job.result, job.error = "running", "", ""
            yield "Done: OLD_JOB.mp4\n"
            yield "Error: OLD_JOB error\n"

    job.proc = SimpleNamespace(stdout=LateOutput(), wait=lambda: 1, poll=lambda: 1)
    job._read()
    snap = job.snapshot()
    assert snap["result"] == snap["error"] == ""
    assert snap["lines"] == []


def test_reader_thread_is_bound_to_its_own_child(tmp_path, monkeypatch):
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path / "state"))
    prefs = server.load_prefs()
    prefs.update(output=str(tmp_path / "videos"), by_player=False)
    child = SimpleNamespace(stdout=iter([]), poll=lambda: None)
    captured = []

    class DelayedThread:
        def __init__(self, target, args=(), **kwargs):
            captured.append(args)
        def start(self):
            pass

    monkeypatch.setattr(server.subprocess, "Popen", lambda *a, **kw: child)
    monkeypatch.setattr(server.threading, "Thread", DelayedThread)
    job = server.Job()
    job.start({"name": "Player", "path": "fixture.dem", "steamid": "111"}, prefs)
    assert captured == [(child,)]
