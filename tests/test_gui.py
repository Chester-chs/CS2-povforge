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
