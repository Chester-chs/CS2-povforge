import tomllib

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
