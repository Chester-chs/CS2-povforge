import tomllib
from pathlib import Path

from povforge.config import load_config

from povforge.gui import server


def test_rounds_spec():
    assert server.rounds_spec([3, 1, 2, 7, 9, 10]) == "1-3,7,9-10"
    assert server.rounds_spec([5]) == "5"


def test_unpacked_dem_next_to_zst_is_listed_once(tmp_path):
    (tmp_path / "1-abcdef12-x.dem.zst").write_bytes(b"x")
    (tmp_path / "1-abcdef12-x.dem").write_bytes(b"x")
    (tmp_path / "other.dem").write_bytes(b"x")
    (tmp_path / "notes.txt").write_text("x")
    names = sorted(d["name"] for d in server.find_demos([str(tmp_path)]))
    assert names == ["1-abcdef12-x.dem.zst", "other.dem"]


def test_job_reads_progress_lines():
    j = server.Job()
    j.state = "running"
    for line in ["Reading x.dem ...", "Starting CS2 through HLAE to record 3 clips (~2.0 min of video).",
                 "Recorded r01 (1/3)", "Recorded r02 (2/3)"]:
        j._take(line)
    s = j.snapshot()
    assert s["stage"] == "record" and s["recorded"] == [1, 2] and s["step"] == [2, 3]
    j._take("Composing 2/5")
    assert j.snapshot()["stage"] == "compose"
    j._take("Done: C:\\Videos\\PovForge\\a\\donk_POV.mp4")
    assert j.snapshot()["result"].endswith("donk_POV.mp4")


def test_job_config_is_valid_toml(tmp_path, monkeypatch):
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path))
    prefs = server.load_prefs()
    prefs["output"] = 'C:\\Users\\Chester\\Videos\\Pov "Forge"'
    prefs["keyboard"] = False
    data = tomllib.loads(server.write_job_config(prefs).read_text(encoding="utf-8"))
    assert data["output"]["dir"] == prefs["output"]
    assert data["overlay"]["keyboard"] is False and data["intro"]["enabled"] is True


class FakeJob:
    def __init__(self):
        self.state, self.item, self.started = "idle", 0, []
        self.on_finish = None

    def start(self, item, prefs):
        self.state, self.item = "running", item["id"]
        self.started.append(item["name"])
        self.last = item

    def finish(self, state="done"):
        self.state = state
        self.on_finish()

    def snapshot(self):
        return {"state": self.state, "item": self.item, "result": "v.mp4" if self.state == "done" else "",
                "highlights": "", "cover": "", "description": "", "title": "t", "error": ""}


def test_queue_runs_one_after_another():
    job = FakeJob()
    q = server.Queue(job, {})
    q.add("a.dem", "1", "donk", [], "Cache")
    q.add("a.dem", "2", "Br4tkO", [1], "Cache")
    assert job.started == ["donk"]
    assert [i["state"] for i in q.snapshot()["items"]] == ["running", "queued"]
    job.finish()
    assert job.started == ["donk", "Br4tkO"]
    assert q.snapshot()["items"][0]["result"] == "v.mp4"


def test_stopping_pauses_the_queue_until_resumed():
    job = FakeJob()
    q = server.Queue(job, {})
    q.add("a.dem", "1", "a", [], "")
    q.add("a.dem", "2", "b", [], "")
    job.finish("cancelled")
    assert job.started == ["a"] and q.snapshot()["paused"]
    q.resume()
    assert job.started == ["a", "b"]
    q.retry(1)                     # the stopped one goes back into the queue
    assert q.snapshot()["items"][0]["state"] == "queued"


def test_version_compare():
    assert server._version_tuple("v0.10.0") > server._version_tuple("0.9.3")


class _Resp:
    def __init__(self, body: bytes, url: str = ""):
        self.body, self._url = body, url
        self.headers = {"Content-Length": str(len(body))}

    def read(self, n=-1):
        out, self.body = (self.body, b"") if n < 0 else (self.body[:n], self.body[n:])
        return out

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _release_api(monkeypatch, setup_url, payload=b"installer", digest=None):
    import hashlib
    import json
    import urllib.request
    release = {"tag_name": "v9.9.9", "html_url": "https://github.com/Chester-chs/CS2-povforge/releases/tag/v9.9.9",
               "body": "**What's new in v9.9.9 / 本次更新**\n\nFaster.\n更快。\n\n**Windows / Windows 程序**\n\nhow to install",
               "assets": [{"name": "PovForge-Setup.exe", "browser_download_url": setup_url, "size": len(payload),
                           "digest": digest or "sha256:" + hashlib.sha256(payload).hexdigest()}]}

    def fake_urlopen(req, timeout=0):
        url = req.full_url if hasattr(req, "full_url") else req
        if url == server.RELEASES_API:
            return _Resp(json.dumps(release).encode())
        return _Resp(payload)
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)


def test_latest_release_reads_installer_and_notes(monkeypatch):
    url = server.DOWNLOADS + "v9.9.9/PovForge-Setup.exe"
    _release_api(monkeypatch, url)
    info = server.latest_release()
    assert info["version"] == "9.9.9" and info["setup"] == url and info["size"] == 9 and len(info["sha256"]) == 64
    assert info["notes"] == "Faster.\n更快。"           # what's new only


def test_latest_release_ignores_installers_from_elsewhere(monkeypatch):
    _release_api(monkeypatch, "https://evil.example/PovForge-Setup.exe")
    assert server.latest_release()["setup"] == ""


def _wait(up, states, also=lambda: True):
    import threading
    for _ in range(250):
        if up.status()["state"] in states and also():
            return up.status()
        threading.Event().wait(0.02)
    return up.status()


def test_updater_downloads_checks_and_runs_the_installer(monkeypatch):
    _release_api(monkeypatch, server.DOWNLOADS + "v9.9.9/PovForge-Setup.exe")
    ran, quit_ = [], []
    monkeypatch.setattr(server, "can_self_update", lambda: True)
    monkeypatch.setattr(server, "run_installer", lambda p: ran.append(p.read_bytes()))
    monkeypatch.setattr(server.time, "sleep", lambda s: None)
    up = server.Updater("0.8.4", busy=lambda: False, quit_app=lambda: quit_.append(1))
    assert up.check()["state"] == "available"
    up.install()
    st = _wait(up, ("installing", "error"), also=lambda: bool(quit_) or up.status()["state"] == "error")
    assert st["state"] == "installing" and ran == [b"installer"] and quit_ == [1]


def test_updater_refuses_a_bad_checksum(monkeypatch):
    _release_api(monkeypatch, server.DOWNLOADS + "v9.9.9/PovForge-Setup.exe", digest="sha256:" + "0" * 64)
    ran = []
    monkeypatch.setattr(server, "run_installer", lambda p: ran.append(p))
    up = server.Updater("0.8.4", busy=lambda: False, quit_app=lambda: None)
    up.check()
    up.install()
    st = _wait(up, ("error",))
    assert st["state"] == "error" and "checksum" in st["error"] and not ran


def test_updater_waits_while_recording(monkeypatch):
    _release_api(monkeypatch, server.DOWNLOADS + "v9.9.9/PovForge-Setup.exe")
    up = server.Updater("0.8.4", busy=lambda: True, quit_app=lambda: None)
    up.check()
    st = up.install()
    assert st["state"] == "available" and st["error"] == "busy"


def test_no_update_when_current(monkeypatch):
    _release_api(monkeypatch, server.DOWNLOADS + "v9.9.9/PovForge-Setup.exe")
    assert server.Updater("10.0.0", busy=lambda: False, quit_app=lambda: None).check()["state"] == "current"


def test_reel_items_go_through_the_queue():
    job = FakeJob()
    q = server.Queue(job, {})
    q.add_reel("donk 集锦", [{"demo": "a.dem", "steamid": "1", "round": 18}, {"demo": "b.dem", "steamid": "1", "round": 3}])
    assert job.started == ["donk 集锦"] and job.last["kind"] == "reel"
    assert [i["round"] for i in job.last["reel"]] == [18, 3]      # the user's order is kept


def test_reel_effects_go_with_it():
    job = FakeJob()
    q = server.Queue(job, {})
    q.add_reel("r", [{"demo": "a.dem", "steamid": "1", "round": 2}], fx={"transition": "flash", "junk": 1})
    fx = job.last["effects"]
    assert fx["transition"] == "flash" and "junk" not in fx and fx["outro"] == "none"


def test_job_reads_effects_progress():
    j = server.Job()
    for line in ["Effects: moment 2/5", "Effects: joining the picture ..."]:
        j._take(line)
        if line.startswith("Effects: moment"):
            assert j.snapshot()["step"] == [2, 5]
    assert j.snapshot()["stage"] == "cut"


def test_job_reads_reel_progress():
    j = server.Job()
    for line in ["Reel source 2/3: x.dem", "Cutting the reel 4/7", "Done: C:/v/r.mp4"]:
        j._take(line)
    snap = j.snapshot()
    assert snap["stage"] == "cut" and snap["step"] == [4, 7] and snap["result"] == "C:/v/r.mp4"
    assert snap["source"] == [2, 3]


def test_clean_work_only_removes_the_work_folder(tmp_path):
    prefs = {"output": str(tmp_path)}
    (tmp_path / "donk_POV.mp4").write_text("video")
    w = server.work_dir(prefs)
    (w / "job" / "clips").mkdir(parents=True)
    (w / "job" / "clips" / "clip_000.mp4").write_text("x" * 100)
    assert server.folder_size(w) == 100
    assert server.clean_work(prefs) == 100
    assert not w.exists() and (tmp_path / "donk_POV.mp4").read_text() == "video"


def test_config_and_app_agree_on_the_work_folder():
    from povforge.config import Config
    assert Config().work_dir_name == server.WORK_DIR_NAME


def test_first_run_asks_for_folders_but_old_installs_keep_theirs(tmp_path, monkeypatch):
    import json
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path))
    assert server.load_prefs()["folders_set"] is False            # brand new
    server.app_dir().mkdir(parents=True)
    (server.app_dir() / "app.json").write_text(json.dumps({"output": "D:/v"}), encoding="utf-8")
    p = server.load_prefs()
    assert p["folders_set"] is True and p["output"] == "D:/v"     # set up by an older version


class _Proc:
    def __init__(self, alive=True):
        self.alive = alive

    def poll(self):
        return None if self.alive else 0


def _app(monkeypatch, tmp_path):
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path))
    def offline():
        raise RuntimeError("offline")
    monkeypatch.setattr(server, "latest_release", offline)     # no network in tests
    return server.App()


def test_app_stays_while_its_window_is_open_even_without_pings(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    app.window = _Proc(alive=True)
    assert app.quit_reason(app.last_seen + 3600) == ""          # hidden window, page throttled for an hour
    app.window.alive = False
    assert app.quit_reason(app.last_seen + 20) == "window closed"


def test_app_without_a_watched_window_waits_minutes_not_seconds(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    assert app.quit_reason(app.last_seen + 60) == ""
    assert app.quit_reason(app.last_seen + 200) != ""


def test_closing_the_page_quits_soon_but_a_reload_does_not(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    app.window = _Proc(alive=True)                              # e.g. the browser keeps running
    app.bye_at = app.last_seen + 1
    assert app.quit_reason(app.bye_at + 10) == "window closed"
    app.last_seen = app.bye_at + 2                              # the reloaded page checked in
    assert app.quit_reason(app.bye_at + 10) == ""


def test_never_quits_while_busy(monkeypatch, tmp_path):
    app = _app(monkeypatch, tmp_path)
    app.inspecting = 1
    assert app.quit_reason(app.last_seen + 10_000) == ""


def test_demo_reading_is_saved_for_next_time(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path / "state"))
    demo = tmp_path / "m.dem"
    demo.write_bytes(b"x")
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout='{"map": "de_cache", "rounds": 23}\n', stderr="")
    monkeypatch.setattr(server.subprocess, "run", fake_run)
    server._inspect_cache.clear()
    assert server.inspect_isolated(str(demo), tmp_path)["rounds"] == 23
    server._inspect_cache.clear()                     # as if the app was restarted
    assert server.inspect_isolated(str(demo), tmp_path)["map"] == "de_cache"
    assert len(calls) == 1                            # the demo was read only once


def test_updater_prefers_the_incremental_update_and_falls_back(monkeypatch):
    from povforge import selfupdate
    _release_api(monkeypatch, server.DOWNLOADS + "v9.9.9/PovForge-Setup.exe")
    ran, applied, quit_ = [], [], []
    monkeypatch.setattr(server, "can_self_update", lambda: True)
    monkeypatch.setattr(server, "run_installer", lambda p: ran.append(p))
    monkeypatch.setattr(server.time, "sleep", lambda s: None)
    monkeypatch.setattr(selfupdate, "apply", lambda *a, **k: applied.append(a))

    up = server.Updater("0.8.4", busy=lambda: False, quit_app=lambda: quit_.append(1))
    up.check()
    up.info["zip"] = server.DOWNLOADS + "v9.9.9/PovForge-windows.zip"
    monkeypatch.setattr(selfupdate, "prepare", lambda *a, **k: {"version": "9.9.9", "changed": ["PovForge.exe"],
                                                                "removed": [], "bytes": 5 << 20})
    up.install()
    _wait(up, ("installing", "error"), also=lambda: bool(quit_))
    assert applied and not ran                                   # only the changed files, no installer

    def broken(*a, **k):
        raise RuntimeError("no partial downloads")
    monkeypatch.setattr(selfupdate, "prepare", broken)
    quit_.clear(); applied.clear()
    up2 = server.Updater("0.8.4", busy=lambda: False, quit_app=lambda: quit_.append(1))
    up2.check()
    up2.info["zip"] = server.DOWNLOADS + "v9.9.9/PovForge-windows.zip"
    up2.install()
    _wait(up2, ("installing", "error"), also=lambda: bool(quit_))
    assert ran and not applied                                   # fell back to the full installer


def test_update_works_without_a_check_through_the_updater_first(monkeypatch):
    """The bug in 0.10.1: the startup check lit the Update button, but the updater
    itself had never checked, so Update did nothing and the page spun forever."""
    _release_api(monkeypatch, server.DOWNLOADS + "v9.9.9/PovForge-Setup.exe")
    ran, quit_ = [], []
    monkeypatch.setattr(server, "can_self_update", lambda: True)
    monkeypatch.setattr(server, "run_installer", lambda p: ran.append(p))
    monkeypatch.setattr(server.time, "sleep", lambda s: None)
    up = server.Updater("0.8.4", busy=lambda: False, quit_app=lambda: quit_.append(1))
    assert up.status()["state"] == "idle"
    st = up.install()                                   # straight from "idle"
    assert st["state"] in ("downloading", "installing")
    _wait(up, ("installing", "error"), also=lambda: bool(quit_))
    assert ran


def test_app_startup_check_readies_the_updater(monkeypatch, tmp_path):
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path))
    _release_api(monkeypatch, server.DOWNLOADS + "v9.9.9/PovForge-Setup.exe")
    app = server.App()
    for _ in range(100):
        if app.update:
            break
        threading_wait(0.02)
    assert app.update["version"] == "9.9.9" and app.updater.status()["state"] == "available"


def threading_wait(s):
    import threading
    threading.Event().wait(s)


def test_cli_output_reaches_the_app_as_utf8():
    from pathlib import Path
    """The app reads the command-line program's output as UTF-8; on Chinese Windows
    a path like 职业选手POV arrived garbled and Play/Show in folder found nothing."""
    import os, subprocess, sys
    env = dict(os.environ, PYTHONIOENCODING="gbk")       # what Windows would use otherwise
    code = "from povforge.cli import _utf8_output; _utf8_output(); print('Done: C:/职业选手POV/donk666 高光集锦.mp4')"
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, env=env,
                       cwd=str(Path(__file__).resolve().parents[1]))
    assert r.stdout.decode("utf-8").strip() == "Done: C:/职业选手POV/donk666 高光集锦.mp4"


# --- a folder per player --------------------------------------------------------------

def _job(work, name, sid, pname, video=None):
    import json
    j = work / name
    j.mkdir(parents=True)
    (j / "plan.json").write_text(json.dumps({"player": {"steamid": sid, "name": pname}}), encoding="utf-8")
    if video:
        (j / "published.json").write_text(json.dumps({"video": video}), encoding="utf-8")
    return j


def test_videos_go_into_the_players_folder(tmp_path):
    prefs = {"output": str(tmp_path), "player_folders": {}, "lang": "zh"}
    assert server.videos_folder(prefs, {"kind": "match", "steamid": "1", "name": "donk666"}) == tmp_path / "donk666"
    # a new nickname keeps the same folder; another player with that name gets their own
    assert server.videos_folder(prefs, {"kind": "match", "steamid": "1", "name": "donk"}) == tmp_path / "donk666"
    assert server.videos_folder(prefs, {"kind": "match", "steamid": "2", "name": "donk666"}) == tmp_path / "donk666 (2)"
    one = {"kind": "reel", "reel": [{"steamid": "1", "name": "donk"}, {"steamid": "1"}]}
    many = {"kind": "reel", "reel": [{"steamid": "1"}, {"steamid": "3", "name": "m0NESY"}]}
    assert server.videos_folder(prefs, one) == tmp_path / "donk666"
    assert server.videos_folder(prefs, many) == tmp_path / "多人集锦"
    assert server.videos_folder({**prefs, "by_player": False}, one) is None


def test_job_config_names_the_videos_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path))
    prefs = {**server.load_prefs(), "output": str(tmp_path / "out")}
    cfg = load_config(server.write_job_config(prefs, tmp_path / "out" / "donk"))
    from povforge import pipeline
    assert pipeline.videos_dir(cfg) == tmp_path / "out" / "donk" and pipeline.work_root(cfg) == tmp_path / "out" / "工作文件"


def test_rename_player_folder_moves_and_merges(tmp_path):
    prefs = {"output": str(tmp_path), "player_folders": {"1": {"folder": "donk666", "name": "donk666"}}}
    (tmp_path / "donk666").mkdir()
    (tmp_path / "donk666" / "a.mp4").write_text("a")
    (tmp_path / "donk").mkdir()
    (tmp_path / "donk" / "old.mp4").write_text("o")
    server.rename_player_folder(prefs, "1", "donk")
    assert prefs["player_folders"]["1"]["folder"] == "donk"
    assert sorted(p.name for p in (tmp_path / "donk").iterdir()) == ["a.mp4", "old.mp4"]
    assert not (tmp_path / "donk666").exists()


def test_existing_videos_sorted_by_player(tmp_path):
    out = tmp_path / "PovForge"
    work = out / "工作文件"
    _job(work, "a__donk666", "1", "donk666", "donk666_mirage.mp4")
    _job(work, "b__m0NESY", "2", "m0NESY", "m0NESY_dust2.mp4")
    for n in ("donk666_mirage.mp4", "donk666_mirage.jpg", "m0NESY_dust2.mp4", "donk666 高光集锦.mp4"):
        (out / n).write_text("x")
    prefs = {"output": str(out), "player_folders": {}}
    server.organize_existing(prefs)
    assert prefs["output"] == str(out) and prefs["organized"]
    assert sorted(p.name for p in (out / "donk666").iterdir()) == ["donk666 高光集锦.mp4", "donk666_mirage.jpg", "donk666_mirage.mp4"]
    assert [p.name for p in (out / "m0NESY").iterdir()] == ["m0NESY_dust2.mp4"]


def test_a_players_own_folder_is_kept_as_theirs(tmp_path):
    """.../Pro POV/donk with only donk666's videos: that folder becomes donk666's,
    the output folder moves up one, and the work files go with it."""
    out = tmp_path / "职业选手POV" / "donk"
    work = out / "工作文件"
    _job(work, "a__donk666", "1", "donk666", "x.mp4")
    (work / "demos").mkdir()
    (work / "demos" / "m.dem").write_text("d")
    (out / "x.mp4").write_text("v")
    (out / "donk666 高光集锦.mp4").write_text("v")
    prefs = {"output": str(out), "player_folders": {}}
    server.organize_existing(prefs)
    assert prefs["output"] == str(tmp_path / "职业选手POV")
    assert prefs["player_folders"]["1"]["folder"] == "donk"
    assert (out / "x.mp4").exists() and not (out / "工作文件").exists()
    assert (tmp_path / "职业选手POV" / "工作文件" / "a__donk666" / "plan.json").exists()


def test_a_moved_work_folder_still_finds_its_demo(tmp_path):
    import json
    from povforge import pipeline
    job = tmp_path / "工作文件" / "j"
    job.mkdir(parents=True)
    (tmp_path / "工作文件" / "demos").mkdir()
    (tmp_path / "工作文件" / "demos" / "m.dem").write_text("d")
    plan = {"demo_path": "C:/old/place/工作文件/demos/m.dem", "map_name": "de_dust2", "tickrate": 64.0,
            "player": {"steamid": "1", "name": "p"}, "segments": []}
    (job / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    assert Path(pipeline.load_plan(job).demo_path) == (tmp_path / "工作文件" / "demos" / "m.dem").resolve()


# --- recording size and quality ------------------------------------------------------------

def test_recording_size_fits_the_screen(monkeypatch):
    assert server.record_size({"record_res": "auto"}, (2560, 1440)) == (1920, 1080)
    assert server.record_size({"record_res": "2160"}, (2560, 1440)) == (1920, 1080)
    assert server.record_size({"record_res": "1080"}, (3840, 2160)) == (1920, 1080)
    assert server.record_size({"record_res": "auto"}, (3440, 1440)) == (1920, 1080)
    monkeypatch.setattr(server, "screen_size", lambda: None)
    assert server.record_size({"record_res": "auto"}, None) == (1920, 1080)           # screen unknown
    monkeypatch.setattr(server, "screen_size", lambda: (1280, 720))
    assert server.record_size({"record_res": "auto"}) == (1920, 1080)


def test_job_config_quality(tmp_path, monkeypatch):
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path))
    monkeypatch.setattr(server, "screen_size", lambda: (2560, 1440))
    prefs = {**server.load_prefs(), "output": str(tmp_path), "record_res": "1440", "record_fps": 120}
    cfg = load_config(server.write_job_config(prefs))
    assert (cfg.record.width, cfg.record.height, cfg.record.fps) == (1920, 1080, 120)
    assert "-crf 12" in cfg.record.video_options and cfg.compose.crf == 15 and cfg.compose.preset == "medium"
    assert cfg.upload.upscale == 0
    cfg = load_config(server.write_job_config({**prefs, "record_res": "1080", "record_fps": 60, "upload_4k": False}))
    assert (cfg.record.height, cfg.compose.preset, cfg.upload.upscale) == (1080, "medium", 0)
