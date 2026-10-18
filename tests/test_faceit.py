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
    (tmp_path / "faceit_match.json").write_text('{"startedAt": "2026-10-16T22:46:18Z"}')
    monkeypatch.setattr(faceit, "screenshot_room", lambda *a, **k: 1 / 0)
    assert pipeline.faceit_screenshot(Config(), tmp_path, "1-x") == tmp_path / "faceit_room.png"


def test_match_time_in_a_time_zone():
    info = {"startedAt": "2026-10-16T22:46:18Z"}
    assert faceit.match_time(info, "Europe/London").strftime("%H:%M") == "23:46"
    assert faceit.match_time(info, "Asia/Shanghai").strftime("%m-%d %H:%M") == "10-17 06:46"
    assert faceit.match_time({}) is None


def test_intro_date_prefers_the_match_time(tmp_path):
    cfg = Config()
    cfg.intro.timezone = "Europe/London"
    assert pipeline.intro_date(cfg, tmp_path, {"date": "2026-10-18"}) == "2026-10-18"
    (tmp_path / "faceit_match.json").write_text('{"startedAt": "2026-10-16T22:46:18Z"}')
    assert pipeline.intro_date(cfg, tmp_path, {"date": "2026-10-18"}) == "2026年10月16日 23:46"
