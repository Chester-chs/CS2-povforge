import json
import shutil
import subprocess
from pathlib import Path

import pytest

from povforge import effects as E
from povforge.compose import ComposeSettings

FFMPEG = shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="needs FFmpeg")


# --- settings -----------------------------------------------------------------

def test_normalize_fills_in_and_clamps():
    fx = E.normalize({"transition": "flash", "transition_seconds": 9, "slowmo_speed": "0.1",
                      "grade": "nonsense", "bogus": 1, "transitions": {"2": "black", "x": "flash", "3": "nope"}})
    assert fx["transition"] == "flash" and fx["transition_seconds"] == 1.5
    assert fx["slowmo_speed"] == 0.2 and fx["grade"] == "none"
    assert "bogus" not in fx and fx["transitions"] == {"2": "black"}
    assert set(fx) == set(E.DEFAULTS)


def test_match_grade_needs_the_reference_numbers():
    assert E.normalize({"grade": "match"})["grade"] == "none"
    fx = E.normalize({"grade": "match", "grade_match": {"sat": 30, "luma": 100, "spread": 150, "u": 120, "v": 135}})
    assert fx["grade"] == "match"


def test_plain_means_the_old_quick_join():
    assert E.is_plain(None) and E.is_plain({}) and E.is_plain({"pace": "tight"})
    assert not E.is_plain({"transition": "dissolve"})
    assert not E.is_plain({"music": "song.mp3"})


def test_presets_are_valid_settings():
    for name, p in E.PRESETS.items():
        fx = E.normalize(p)
        for k, v in p.items():
            assert fx[k] == v, (name, k)


def test_pace():
    assert E.pace_seconds({"pace": "tight"}, 4.0, 1.5) == (2.0, 0.8)
    assert E.pace_seconds({}, 4.0, 1.5) == (4.0, 1.5)


# --- timing ---------------------------------------------------------------------

def test_slow_motion_time_map():
    parts = E.time_map(10.0, [3.0, 3.2, 8.0], 0.5)
    # the two close kills share one slow part
    slow = [(a, b) for a, b, s in parts if s == 0.5]
    assert slow == [(3.0 - E.SLOW_BEFORE, 3.2 + E.SLOW_AFTER), (8.0 - E.SLOW_BEFORE, 8.0 + E.SLOW_AFTER)]
    assert parts[0][0] == 0 and parts[-1][1] == 10.0
    slow_len = sum(b - a for a, b in slow)
    assert E.mapped_length(parts) == pytest.approx(10.0 + slow_len)
    # times before the first slow part don't move; after it they are later
    assert E.mapped(1.0, parts) == pytest.approx(1.0)
    assert E.mapped(10.0, parts) == pytest.approx(E.mapped_length(parts))
    assert E.time_map(5.0, [], 0.5) == [(0.0, 5.0, 1.0)]


def test_setpts_expression_is_piecewise():
    parts = E.time_map(10.0, [5.0], 0.5)
    expr = E.setpts_expr(parts)
    assert expr.startswith("(if(lt(T,") and expr.endswith(")/TB")
    assert E.setpts_expr([(0.0, 4.0, 1.0)]) == "PTS-STARTPTS"


def test_atempo_chain_stays_in_range():
    assert E.atempo_chain(0.5) == "atempo=0.5"
    assert E.atempo_chain(0.25) == "atempo=0.5,atempo=0.5"
    assert E.atempo_chain(1.0) == "anull"


def test_which_kills_get_effects():
    ms = [E.Moment(Path("a"), 0, 10, [2, 5]), E.Moment(Path("b"), 0, 10, [1, 7, 9])]
    assert E.chosen_kills(ms, "all") == [[2, 5], [1, 7, 9]]
    assert E.chosen_kills(ms, "last") == [[5], [9]]
    assert E.chosen_kills(ms, "final") == [[], [9]]


def test_grade_match_moves_towards_the_reference():
    fx = E.normalize({"grade": "match", "grade_match": {"sat": 60, "luma": 128, "spread": 200, "u": 128, "v": 128}})
    f = E.grade_filter(fx, {"sat": 30, "luma": 128, "spread": 100, "u": 128, "v": 128})
    assert "saturation=2" in f and "contrast=1.6" in f
    assert E.grade_filter(fx, None) == ""


# --- putting a reel together ----------------------------------------------------------

def _clip(path: Path, hue: int, seconds: float = 6.0) -> Path:
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    f"testsrc2=s=480x270:r=30,hue=h={hue}", "-f", "lavfi", "-i", "sine=f=440:sample_rate=48000",
                    "-t", str(seconds), "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-ac", "2", str(path)],
                   check=True)
    return path


def _durations(path: Path) -> tuple[float, float]:
    out = subprocess.run([FFMPEG.replace("ffmpeg", "ffprobe"), "-v", "error", "-show_entries",
                          "stream=codec_type,duration", "-of", "json", str(path)], capture_output=True, text=True)
    st = {s["codec_type"]: float(s["duration"]) for s in json.loads(out.stdout)["streams"]}
    return st["video"], st["audio"]


@needs_ffmpeg
def test_reel_with_effects_keeps_sound_and_picture_together(tmp_path):
    clips = [_clip(tmp_path / f"c{i}.mp4", i * 120) for i in range(3)]
    moments = [E.Moment(clips[0], 0.5, 4.5, [1.5, 3.0]), E.Moment(clips[1], 1.0, 4.0, [2.0]),
               E.Moment(clips[2], 0.0, 5.0, [2.5])]
    fx = {"intro": "title", "transition": "dissolve", "transition_seconds": 0.5, "kill_slowmo": True,
          "kill_zoom": True, "kill_flash": True, "outro": "freeze", "letterbox": True, "grade": "vivid",
          "transitions": {"2": "flash"}}
    out = E.build(moments, fx, tmp_path / "reel.mp4", tmp_path / "work", (480, 270), 30,
                  ComposeSettings(preset="ultrafast"), title="测试 Test")
    v, a = _durations(out)
    # card 2.5 + moments (with 2 slowed kills each 0.55 s longer) + freeze 2 - three joins of 0.5
    slow = (E.SLOW_BEFORE + E.SLOW_AFTER)
    expect = 2.5 + (4 + 2 * slow) + (3 + slow) + (5 + slow) + 2.0 - 3 * 0.5
    assert v == pytest.approx(expect, abs=0.1)
    assert a == pytest.approx(v, abs=0.05)


@needs_ffmpeg
def test_reel_with_music(tmp_path):
    clips = [_clip(tmp_path / f"c{i}.mp4", i * 120, 4) for i in range(2)]
    song = tmp_path / "song.m4a"
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=220:sample_rate=44100",
                    "-t", "2", str(song)], check=True)       # shorter than the reel: it loops
    moments = [E.Moment(c, 0.0, 4.0, [2.0]) for c in clips]
    out = E.build(moments, {"transition": "black", "music": str(song), "game_audio": "mute"}, tmp_path / "r.mp4",
                  tmp_path / "w", (320, 180), 30, ComposeSettings(preset="ultrafast"))
    v, a = _durations(out)
    assert v == pytest.approx(8 - 0.4, abs=0.1) and a == pytest.approx(v, abs=0.05)


@needs_ffmpeg
def test_the_style_of_a_reel_is_read_back(tmp_path):
    """The analyser finds the effects the engine put in."""
    from povforge import style
    clips = [_clip(tmp_path / f"c{i}.mp4", i * 120, 7) for i in range(3)]
    moments = [E.Moment(clips[0], 0.0, 6.0, [3.0]), E.Moment(clips[1], 0.5, 6.5, [3.0]),
               E.Moment(clips[2], 0.0, 6.0, [3.0])]
    fx = {"intro": "fade", "transition": "flash", "transition_seconds": 0.4, "outro": "freeze"}
    out = E.build(moments, fx, tmp_path / "reel.mp4", tmp_path / "work", (480, 270), 30,
                  ComposeSettings(preset="ultrafast"))
    got = style.analyze(out, FFMPEG)["effects"]
    assert got["intro"] == "fade"
    assert got["transition"] == "flash"
    assert got["transition_seconds"] == pytest.approx(0.4, abs=0.15)
    assert got["outro"] == "freeze"
    assert got["grade"] == "match" and "sat" in got["grade_match"]


def test_join_list_lines_escape_quotes(tmp_path):
    from povforge.compose import concat_line
    line = concat_line(tmp_path / "it's" / "a.mp4")
    assert line.startswith("file '") and line.endswith("'\n") and "it'\\''s" in line
