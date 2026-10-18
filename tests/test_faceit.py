from pathlib import Path

from povforge import faceit, pipeline
from povforge.config import Config


def test_match_id_from_file_names():
    mid = "1-a34d80c7-3b13-4d61-a987-5f907440193a"
    assert faceit.match_id(f"{mid}-1-1.dem.zst") == mid
    assert faceit.match_id(Path("C:/Users/x/Downloads") / f"{mid.upper()}-1-1.dem") == mid
    assert faceit.match_id("g2-vs-falcons-m1-dust2.dem") is None
    assert faceit.room_url(mid).endswith(f"/room/{mid}/scoreboard")


def test_screenshot_failure_falls_back(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("blocked")
    monkeypatch.setattr(faceit, "screenshot_room", boom)
    assert pipeline.faceit_screenshot(Config(), tmp_path, "1-x") is None
    assert pipeline.faceit_screenshot(Config(), tmp_path, None) is None


def test_existing_screenshot_is_reused(tmp_path, monkeypatch):
    (tmp_path / "faceit_room.png").write_bytes(b"png")
    monkeypatch.setattr(faceit, "screenshot_room", lambda *a, **k: 1 / 0)
    assert pipeline.faceit_screenshot(Config(), tmp_path, "1-x") == tmp_path / "faceit_room.png"
