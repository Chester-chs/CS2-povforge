"""A chosen background track that has gone missing stops the reel before
recording, instead of publishing it silently without music."""
import pytest

from povforge import effects, reel
from povforge.reel import ReelItem


def test_check_music_accepts_none_and_existing(tmp_path):
    effects.check_music(None)
    effects.check_music({"music": ""})
    track = tmp_path / "song.m4a"
    track.write_bytes(b"x")
    effects.check_music({"music": str(track)})


def test_check_music_rejects_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="Background music not found"):
        effects.check_music({"music": str(tmp_path / "gone.m4a")})


def test_cli_reports_missing_music_as_a_readable_error_not_a_crash(tmp_path, capsys, monkeypatch):
    import json
    from povforge import cli
    monkeypatch.setattr(cli, "_restore_leftover_settings", lambda: None)
    spec = tmp_path / "reel.json"
    spec.write_text(json.dumps({"title": "t", "items": [{"demo": str(tmp_path / "a.dem"), "steamid": "1", "round": 1}],
                                "effects": {"music": str(tmp_path / "gone.m4a")}}), encoding="utf-8")
    assert cli.main(["reel", str(spec)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("Error: ") and "找不到背景音乐文件" in err


@pytest.mark.parametrize("mode", ["kills", "kills_deaths"])
def test_reel_stops_before_recording(tmp_path, monkeypatch, mode):
    class Record:
        def limit_output(self):
            pass

    class Cfg:
        record = Record()

    def boom(*a, **kw):
        pytest.fail("nothing may be read or recorded when the music is missing")

    monkeypatch.setattr(reel.pipeline, "make_plan", boom)
    monkeypatch.setattr(reel.pipeline, "whole_match_job", boom)
    import povforge.reel_events as reel_events
    monkeypatch.setattr(reel_events, "load_sources", boom)
    item = ReelItem(str(tmp_path / "a.dem"), "1", 3, mode)
    with pytest.raises(FileNotFoundError):
        reel.run(Cfg(), "t", [item], fx={"music": str(tmp_path / "gone.m4a")})
