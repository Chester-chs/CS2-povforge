"""Recovery after the GUI forcibly stops the recording child on Windows."""

import json
import os
from types import SimpleNamespace

import pytest

from povforge import hlae, settings_guard
from povforge.gui import server


def pending_files(tmp_path, monkeypatch, original_cfg=b"original job cfg"):
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path / "state"))
    steam = tmp_path / "steam"
    folder = steam / "userdata" / "1" / "730" / "local" / "cfg"
    folder.mkdir(parents=True)
    user = folder / "cs2_user_convars.vcfg"
    user.write_bytes(b"original user settings")
    csgo = tmp_path / "game" / "csgo"
    (csgo / "cfg").mkdir(parents=True)
    cfg = csgo / "cfg" / "povforge_job.cfg"
    if original_cfg is not None:
        cfg.write_bytes(original_cfg)
    settings_guard.backup(steam, csgo)
    user.write_bytes(b"recording settings")
    cfg.write_bytes(b"temporary director script")
    return user, cfg


@pytest.mark.parametrize("original_cfg", [None, b"original job cfg"])
def test_guard_restores_job_cfg_after_a_hard_stop(tmp_path, monkeypatch, original_cfg):
    _, cfg = pending_files(tmp_path, monkeypatch, original_cfg)
    settings_guard.restore()
    if original_cfg is None:
        assert not cfg.exists()
    else:
        assert cfg.read_bytes() == original_cfg
    assert not settings_guard.pending()


def cancelled_job(monkeypatch, *, game_running=False, child_running=False):
    j = server.Job()
    j.state = "running"
    j.proc = SimpleNamespace(pid=os.getpid(), terminate=lambda: None,
                             poll=lambda: None if child_running else 1)
    monkeypatch.setattr(server.subprocess, "run", lambda *_a, **_kw: SimpleNamespace(returncode=0))
    monkeypatch.setattr(server.time, "sleep", lambda _: None)
    monkeypatch.setattr(hlae, "running_processes", lambda: {"cs2.exe"} if game_running else set())
    return j


def test_cancel_keeps_backup_pending_until_cs2_has_closed(tmp_path, monkeypatch):
    user, _ = pending_files(tmp_path, monkeypatch)
    j = cancelled_job(monkeypatch, game_running=True)
    j.cancel()
    assert user.read_bytes() == b"recording settings"
    assert settings_guard.pending()
    assert j.snapshot()["state"] == "cancelled"
    assert "restore-settings" in j.snapshot()["error"]


def test_cancel_keeps_backup_when_recording_child_has_not_stopped(tmp_path, monkeypatch):
    user, _ = pending_files(tmp_path, monkeypatch)
    j = cancelled_job(monkeypatch, child_running=True)
    j.cancel()
    assert user.read_bytes() == b"recording settings"
    assert settings_guard.pending()
    assert "restore-settings" in j.snapshot()["error"]


def test_cancel_reports_restore_failure_instead_of_hiding_it(tmp_path, monkeypatch):
    pending_files(tmp_path, monkeypatch)
    j = cancelled_job(monkeypatch)

    def failed_restore():
        raise OSError("file locked")

    monkeypatch.setattr(settings_guard, "restore", failed_restore)
    j.cancel()
    assert settings_guard.pending()
    assert "file locked" in j.snapshot()["error"]
    assert "restore-settings" in j.snapshot()["error"]


def test_cancel_restores_settings_after_game_and_child_exit(tmp_path, monkeypatch):
    user, cfg = pending_files(tmp_path, monkeypatch)
    j = cancelled_job(monkeypatch)
    j.cancel()
    assert user.read_bytes() == b"original user settings"
    assert cfg.read_bytes() == b"original job cfg"
    assert not settings_guard.pending()
    assert not j.snapshot()["error"]


def test_cancel_during_geometry_preparation_leaves_user_game_running(tmp_path, monkeypatch):
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path / "state"))
    j = cancelled_job(monkeypatch, game_running=True)
    calls = []
    monkeypatch.setattr(server.subprocess, "run", lambda args, **kw: calls.append(args))
    j.cancel()
    assert not any("cs2.exe" in args for args in calls)
    assert any(str(os.getpid()) in args for args in calls)
    assert not j.snapshot()["error"]
    assert not settings_guard.pending()


def test_backup_records_owner_process_and_matches_only_that_process(tmp_path, monkeypatch):
    pending_files(tmp_path, monkeypatch)
    data = json.loads((settings_guard.guard_dir() / "manifest.json").read_text())
    assert data["owner_pid"] == os.getpid()
    assert settings_guard.owned_by(os.getpid())
    assert not settings_guard.owned_by(os.getpid() + 1)


@pytest.mark.parametrize("owner", [None, "old_process"])
def test_stale_backup_never_authorizes_cancel_to_kill_user_game(tmp_path, monkeypatch, owner):
    user, cfg = pending_files(tmp_path, monkeypatch)
    path = settings_guard.guard_dir() / "manifest.json"
    data = json.loads(path.read_text())
    if owner is None:
        data.pop("owner_pid", None)
    else:
        data["owner_pid"] = os.getpid() + 1
    path.write_text(json.dumps(data))
    before = {p: p.read_bytes() for p in (user, cfg, path)}
    job = cancelled_job(monkeypatch, game_running=True)
    calls = []
    monkeypatch.setattr(server.subprocess, "run", lambda args, **kwargs: calls.append(args))

    job.cancel()

    assert not any("cs2.exe" in args for args in calls)
    assert any(str(os.getpid()) in args for args in calls)
    assert {p: p.read_bytes() for p in before} == before
    assert settings_guard.pending()
    assert "restore-settings" in job.snapshot()["error"]
