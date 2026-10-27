"""Camera planning and real-media assembly contracts (no CS2 is started)."""

import importlib
import importlib.util
import math
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from povforge.compose import ComposeSettings
from povforge.media import probe


def camera_module():
    assert importlib.util.find_spec("povforge.camera") is not None, "Camera planning is not implemented"
    return importlib.import_module("povforge.camera")


def reference(**changes):
    raw = {"mode": "reference", "follow": True, "orbit": True, "wide": True,
           "victim": True, "frequency": 1.0}
    raw.update(changes)
    return raw


def planned(camera=None, **changes):
    values = dict(start_tick=640, end_tick=1920, kill_ticks=[1152, 1536],
                  victims=[[1152, "222"], [1536, "333"]], steamid="111",
                  tickrate=64, camera=reference() if camera is None else camera,
                  key="demo with unsafe / characters", index=0)
    values.update(changes)
    return camera_module().plan_shots(**values)


def test_malformed_preferences_never_enable_camera_or_nonfinite_timing():
    normal = camera_module().normalize_camera(
        {"mode": [], "follow": "false", "orbit": 1, "wide": None,
         "frequency": float("nan"),
         "durations": {"follow": float("inf"), "orbit": -99, "wide": 999, "victim": True}})
    assert normal["mode"] == "pov"
    assert normal["victim"] is False
    assert set(normal) == {"mode", "victim", "durations", "placement"}
    assert all(math.isfinite(v) and .3 <= v <= 3 for v in normal["durations"].values())


def test_normalization_does_not_share_nested_values():
    raw = reference(durations={"follow": 1.2})
    normal = camera_module().normalize_camera(raw)
    normal["durations"]["follow"] = 2
    assert raw["durations"]["follow"] == 1.2
    assert camera_module().normalize_camera(None)["mode"] == "pov"


def test_pov_mode_and_empty_kills_do_not_plan_extra_recordings():
    assert planned(camera={"mode": "pov", "follow": True}) == []
    assert planned(kill_ticks=[]) == []
    assert planned(camera=reference(frequency=0, victim=False)) == []


@pytest.mark.parametrize("mode", ["pov", "reference"])
def test_victim_replays_cover_every_known_kill_independently_of_camera_density(mode):
    shots = planned(camera=reference(mode=mode, frequency=0), index=7,
                    kill_ticks=[1536, 1152, 1280], victims=[[1536, "333"], [1152, "222"]])
    assert [(s["kind"], s["focus"], s["steamid"]) for s in shots] == [
        ("victim", 1152, "222"), ("victim", 1536, "333"),
    ]
    assert all(s["start"] < s["death"] == s["focus"] < s["end"] for s in shots)


def test_disabled_victim_replay_never_plans_victim_recordings():
    shots = planned(camera=reference(victim=False))
    assert shots == []


def test_simultaneous_kills_keep_each_distinct_real_victim():
    shots = planned(camera={"victim": True}, kill_ticks=[1152, 1152],
                    victims=[[1152, "222"], [1152, "333"], [1152, "222"], [1152, "invalid"]])
    assert [(s["focus"], s["steamid"]) for s in shots] == [(1152, "222"), (1152, "333")]




def test_victim_replay_is_3s_before_and_1s_after_the_real_victims_death():
    shots = planned(camera=reference(follow=False, orbit=False, wide=False))
    assert shots
    for shot in shots:
        assert shot["cam"] == "pov" and shot["insert"]
        assert shot["steamid"] == {1152: "222", 1536: "333"}[shot["focus"]]
        assert shot["death"] == shot["focus"]
        assert shot["start"] == max(640, shot["focus"] - 3 * 64)
        assert shot["end"] == shot["focus"] + 64  # the body going down, from the victim's view
        assert shot["at"] >= (shot["focus"] - 640) / 64
        assert shot["audio_at"] == (shot["start"] - 640) / 64
    assert planned(camera=reference(follow=False, orbit=False, wide=False), victims=[]) == []
    assert planned(camera=reference(follow=False, orbit=False, wide=False),
                   victims={1152: "111", 1536: ""}) == []




def test_after_death_part_never_runs_past_the_moment():
    shots = planned(start_tick=640, end_tick=1180, kill_ticks=[1152], victims={1152: "222"})
    assert shots[0]["end"] == 1180 and shots[0]["start"] == 1152 - 192
    # A kill on the last tick of the moment has no after-death part to show.
    assert planned(start_tick=640, end_tick=1153, kill_ticks=[1152], victims={1152: "222"})[0]["end"] == 1153
    assert planned(start_tick=640, end_tick=1152, kill_ticks=[1151], victims={1151: "222"})[0]["end"] == 1152


def test_main_player_pov_remains_majority_before_end_replays():
    shots = planned(start_tick=640, end_tick=896, kill_ticks=[768], victims={768: "222"})
    replacement = sum(s["until"] - s["at"] for s in shots if not s["insert"])
    assert 4 - replacement > 4 / 2


FFMPEG = shutil.which("ffmpeg")
pytestmark = pytest.mark.filterwarnings("error")


def make_video(path, color, seconds, audio="sine=frequency=440:sample_rate=48000",
               video_filter=None, fps=20):
    cmd = [FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i",
           f"color=c={color}:s=96x54:r={fps}", "-f", "lavfi", "-i", audio]
    if video_filter:
        cmd += ["-vf", video_filter]
    subprocess.run(cmd + ["-t", str(seconds), "-c:v", "libx264", "-preset", "ultrafast",
                          "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)], check=True)
    return path


def colour_at(path, seconds):
    data = subprocess.run([FFMPEG, "-v", "error", "-ss", str(seconds), "-i", str(path),
                           "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                          check=True, capture_output=True).stdout
    return np.frombuffer(data, dtype=np.uint8).reshape(-1, 3).mean(axis=0)


def sound(path):
    data = subprocess.run([FFMPEG, "-v", "error", "-i", str(path), "-vn", "-ac", "1",
                           "-ar", "48000", "-f", "f32le", "-"],
                          check=True, capture_output=True).stdout
    return np.frombuffer(data, dtype="<f4")






@pytest.mark.skipif(not FFMPEG, reason="needs FFmpeg")
@pytest.mark.parametrize("end", [4, 3.99])
def test_victim_replay_audio_uses_the_recorded_demo_time_not_insertion_time(tmp_path, end):
    base = make_video(tmp_path / "base.mp4", "red", 4,
                      "aevalsrc=0.4*sin(2*PI*(150*t+100*t*t)):s=48000")
    victim = make_video(tmp_path / "victim.mp4", "blue", 1)
    shot = dict(id="shot_victim_test", start=0, end=64, steamid="222", cam="pov",
                focus=65, kind="victim", at=end, until=end, insert=True, audio_at=0.0)
    render_replay = getattr(camera_module(), "render_replay", None)
    assert callable(render_replay), "Separate ending replay rendering is missing"
    replay = render_replay(
        clip=base, start=0, end=end, shot=shot,
        shot_paths={shot["id"]: victim}, actual_starts={shot["id"]: 0},
        tickrate=64, out=tmp_path / "moment.mp4", size=(96, 54), fps=20,
        compose=ComposeSettings(ffmpeg=FFMPEG))
    assert replay is not None, "An ending replay must not depend on rounded main duration"
    result, _, duration, kills = replay
    assert duration == pytest.approx(1, abs=.06) and kills == []
    assert colour_at(result, .5)[2] > 200
    original, rendered = sound(base), sound(result)
    # The standalone replay uses source 0..1s, regardless of its old insertion position.
    assert np.corrcoef(original[2048:24000],
                       rendered[2048:24000])[0, 1] > .97


@pytest.mark.skipif(not FFMPEG, reason="needs FFmpeg")
@pytest.mark.parametrize("actual", [80, 64, None])
def test_late_short_or_unmapped_recording_keeps_pov(tmp_path, capsys, actual):
    camera = camera_module()
    base = make_video(tmp_path / "base.mp4", "red", 3)
    blue = make_video(tmp_path / "shot.mp4", "blue", .5)
    shot = dict(id="shot_orbit_test", start=64, end=128, steamid="111", cam="pov",
                focus=129, kind="victim", at=3, until=3, insert=True, audio_at=1)
    result = camera.render_replay(
        clip=base, start=0, end=3, shot=shot,
        shot_paths={shot["id"]: blue}, actual_starts={} if actual is None else {shot["id"]: actual},
        tickrate=64, out=tmp_path / "moment.mp4", size=(96, 54), fps=20,
        compose=ComposeSettings(ffmpeg=FFMPEG))
    assert result is None
    assert "skipping replay" in capsys.readouterr().out


@pytest.mark.skipif(not FFMPEG, reason="needs FFmpeg")
def test_missing_start_metadata_never_guesses_camera_alignment(tmp_path, capsys):
    camera = camera_module()
    base = make_video(tmp_path / "base.mp4", "red", 3)
    blue = make_video(tmp_path / "shot.mp4", "blue", 2)
    shot = dict(id="shot_orbit_test", start=64, end=128, steamid="111", cam="pov",
                focus=129, kind="victim", at=3, until=3, insert=True, audio_at=1)
    result = camera.render_replay(
        clip=base, start=0, end=3, shot=shot,
        shot_paths={shot["id"]: blue}, actual_starts={},
        tickrate=64, out=tmp_path / "moment.mp4", size=(96, 54), fps=20,
        compose=ComposeSettings(ffmpeg=FFMPEG))
    assert result is None
    assert "skipping replay" in capsys.readouterr().out






@pytest.mark.skipif(not FFMPEG, reason="needs FFmpeg")
def test_long_audio_cannot_hide_missing_camera_video_frames(tmp_path, capsys):
    base = make_video(tmp_path / "base.mp4", "red", 3)
    view = tmp_path / "short-picture.mp4"
    subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=blue:s=96x54:r=20:d=0.5", "-f", "lavfi", "-i",
                    "sine=frequency=440:duration=2", "-c:v", "libx264",
                    "-c:a", "aac", str(view)], check=True)
    shot = dict(id="shot_short_video", start=64, end=128, steamid="111", cam="pov",
                focus=129, kind="victim", at=3, until=3, insert=True, audio_at=1)
    result = camera_module().render_replay(
        clip=base, start=0, end=3, shot=shot,
        shot_paths={shot["id"]: view}, actual_starts={shot["id"]: 64},
        tickrate=64, out=tmp_path / "moment.mp4", size=(96, 54), fps=20,
        compose=ComposeSettings(ffmpeg=FFMPEG))
    assert result is None
    assert "skipping replay" in capsys.readouterr().out


@pytest.mark.skipif(not FFMPEG, reason="needs FFmpeg")
def test_short_late_victim_replay_keeps_actual_audio_time_and_available_frames(tmp_path):
    base = make_video(tmp_path / "base.mp4", "red", 6,
                      "aevalsrc=0.4*sin(2*PI*(150*t+100*t*t)):s=48000")
    victim = make_video(tmp_path / "victim.mp4", "blue", .9)
    shot = dict(id="shot_victim_late", start=0, end=64, steamid="222", cam="pov",
                focus=65, kind="victim", at=1.25, until=1.25, insert=True, audio_at=0.0)
    render_replay = getattr(camera_module(), "render_replay", None)
    assert callable(render_replay), "Separate ending replay rendering is missing"
    result, _, duration, kills = render_replay(
        clip=base, start=1.25, end=5.25, shot=shot,
        shot_paths={shot["id"]: victim}, actual_starts={shot["id"]: 3},
        tickrate=64, out=tmp_path / "moment.mp4", size=(96, 54), fps=20,
        compose=ComposeSettings(ffmpeg=FFMPEG))
    assert duration == pytest.approx(.9, abs=.06)
    assert kills == []
    assert colour_at(result, .5)[2] > 200
    original, rendered = sound(base), sound(result)
    # The moment starts at sample 60000; three late ticks add 2250 samples.
    assert np.corrcoef(original[60000 + 2250 + 2048:60000 + 2250 + 24000],
                       rendered[2048:24000])[0, 1] > .97


@pytest.mark.skipif(not FFMPEG, reason="needs FFmpeg")
@pytest.mark.parametrize("recorded, kept", [(2.5, 2.5), (3.0, 3.0), (1.6, None)])
def test_after_death_tail_may_end_early_but_the_part_before_death_may_not(tmp_path, recorded, kept):
    """CS2 can move the camera off a dead victim; the director then stops the take
    early. Losing (part of) the 1s after death keeps the replay; losing footage
    before the death still rejects it."""
    base = make_video(tmp_path / "base.mp4", "red", 6)
    victim = make_video(tmp_path / f"victim{recorded}.mp4", "blue", recorded)
    shot = dict(id="shot_victim_tail", start=0, end=192, steamid="222", cam="pov",
                focus=128, death=128, kind="victim", at=1.0, until=1.0, insert=True, audio_at=0.0)
    out = camera_module().render_replay(
        clip=base, start=1.0, end=5.0, shot=shot,
        shot_paths={shot["id"]: victim}, actual_starts={shot["id"]: 0},
        tickrate=64, out=tmp_path / "replay.mp4", size=(96, 54), fps=20,
        compose=ComposeSettings(ffmpeg=FFMPEG))
    if kept is None:
        assert out is None  # stopped 0.4s before the death (at 2s): not a usable replay
    else:
        assert out is not None and out[2] == pytest.approx(kept, abs=.06)


@pytest.mark.skipif(not FFMPEG, reason="needs FFmpeg")
def test_replay_stops_before_the_camera_left_the_dead_victim(tmp_path):
    """Where the camera left the victim (cut), the replay ends a safety margin
    earlier, so no frame of another player can appear."""
    base = make_video(tmp_path / "base.mp4", "red", 6)
    victim = make_video(tmp_path / "victim.mp4", "blue", 3.0)
    shot = dict(id="shot_victim_cut", start=0, end=192, steamid="222", cam="pov",
                focus=128, death=128, cut=160.0, kind="victim", at=1.0, until=1.0,
                insert=True, audio_at=0.0)
    out = camera_module().render_replay(
        clip=base, start=1.0, end=5.0, shot=shot,
        shot_paths={shot["id"]: victim}, actual_starts={shot["id"]: 0},
        tickrate=64, out=tmp_path / "replay.mp4", size=(96, 54), fps=20,
        compose=ComposeSettings(ffmpeg=FFMPEG))
    # The camera left at 2.5s; the replay keeps 2.5 - 0.3 = 2.2s (death at 2.0s).
    assert out is not None and out[2] == pytest.approx(2.2, abs=.06)
