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

    def start(self, path, steamid, name, rounds, prefs, item):
        self.state, self.item = "running", item
        self.started.append(name)

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
