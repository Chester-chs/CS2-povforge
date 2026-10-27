"""Camera choices reach recording and composition without changing POV jobs."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from povforge import effects, reel
from povforge.config import Config
from povforge.model import Plan, Player, Segment


def test_camera_settings_survive_spec_loading_without_enabling_by_default(tmp_path):
    spec = tmp_path / "reel.json"
    spec.write_text(json.dumps({"effects": {"camera": {
        "mode": "reference", "orbit": True, "durations": {"orbit": 1.3}
    }}}), encoding="utf-8")
    fx = reel.load_effects(spec)
    assert fx["camera"] == effects.normalize({})["camera"]
    assert effects.normalize({})["camera"]["mode"] == "pov"


def test_pov_selection_ignores_detected_cameras_and_keeps_plain_join():
    assert effects.is_plain({"camera": {"mode": "pov", "orbit": True}})
    assert effects.is_plain({"camera": {"mode": "reference"}})
    assert effects.is_plain({"camera": {"mode": "reference", "follow": True}})


def _sources(tmp_path):
    cfg = Config(output_dir=tmp_path / "output")
    demo = tmp_path / "match.dem"
    demo.write_bytes(b"demo")
    windows, contexts, items = {}, {}, []
    for sid in ("11", "22"):
        job = tmp_path / sid
        job.mkdir()
        clip = job / "clip.mp4"
        clip.write_bytes(b"recording")
        (job / "recorded.json").write_text('{"r01": 1032.0}', encoding="utf-8")
        (job / "victims.json").write_text('[[1280, "33"]]', encoding="utf-8")
        plan = Plan(str(demo), "de_test", 64.0, Player(sid, "Player " + sid),
                    [Segment(1, 1024, 2048, "round_end")])
        item = reel.ReelItem(str(demo), sid, 1)
        key = (item.demo, item.steamid, item.round)
        # Real recording starts at 1032, so the trimmed moment starts at 1096.
        windows[key] = [(clip, 1.0, 9.0, [2.875])]
        contexts[key] = (job, plan)
        items.append(item)
    return cfg, items, windows, contexts


def test_camera_order_batches_players_of_one_demo_and_uses_actual_ticks(tmp_path, monkeypatch):
    from povforge import camera, hlae
    cfg, items, windows, contexts = _sources(tmp_path)
    planned, sessions, renders = [], [], []

    def plan_shots(**kw):
        planned.append(kw)
        return [{"id": "shot_" + kw["steamid"], "start": 1100, "end": 1196,
                 "steamid": kw["steamid"], "cam": "pov", "kind": "victim",
                 "focus": 1280, "at": 0.0625, "until": 1.5625, "insert": True}]

    def record(plan, job, settings, ffmpeg, *, extra_shots, shots_only):
        sessions.append((plan, job, extra_shots, shots_only))
        assert shots_only is True
        assert {s["steamid"] for s in extra_shots} == {"11", "22"}
        paths = []
        for s in extra_shots:
            p = job / "shots" / (s["id"] + ".mp4")
            p.parent.mkdir(exist_ok=True)
            p.write_bytes(b"shot")
            paths.append(p)
        (job / "recorded.json").write_text(
            json.dumps({s["id"]: 1099.5 for s in extra_shots}), encoding="utf-8")
        return paths

    def render_replay(**kw):
        renders.append(kw)
        kw["out"].parent.mkdir(parents=True, exist_ok=True)
        kw["out"].write_bytes(b"composed")
        return kw["out"], 0.0, 8.0, []

    monkeypatch.setattr(camera, "plan_shots", plan_shots)
    monkeypatch.setattr(hlae, "record", record)
    monkeypatch.setattr(camera, "render_replay", render_replay)
    fx = effects.normalize({"camera": {"victim": True, "placement": "end"}})
    order = reel._camera_order(cfg, "Test", items, windows, contexts, fx)
    assert len(sessions) == 1
    assert len(order) == 4 and len(renders) == 2
    assert order[:2] == [w for it in items for w in windows[(it.demo, it.steamid, it.round)]]
    assert [p["start_tick"] for p in planned] == [1096, 1096]
    assert [p["kill_ticks"] for p in planned] == [[1280], [1280]]
    assert all(r["actual_starts"][r["shot"]["id"]] == 1099.5 for r in renders)
    assert order[0][0] != order[1][0]


@pytest.mark.parametrize("placeholder,mode,victim", [(False, "pov", False), (False, "reference", False),
                                                      (True, "reference", True)])
def test_disabled_or_placeholder_cameras_never_start_cs2(tmp_path, monkeypatch, placeholder, mode, victim):
    from povforge import hlae
    cfg, items, windows, contexts = _sources(tmp_path)
    monkeypatch.setattr(hlae, "record", lambda *a, **kw: pytest.fail("CS2 must not start"))
    fx = effects.normalize({"camera": {"mode": mode, "follow": True, "victim": victim}})
    order = reel._camera_order(cfg, "Test", items, windows, contexts, fx, placeholder)
    assert order == [windows[(it.demo, it.steamid, it.round)][0] for it in items]


def test_all_planned_camera_kinds_are_accepted_by_recording_contract(tmp_path):
    from povforge import camera, hlae
    shots = camera.plan_shots(
        start_tick=640, end_tick=1920, kill_ticks=[1152, 1536],
        victims=[[1152, "222"], [1536, "333"]], steamid="111", tickrate=64,
        camera={"mode": "reference", "follow": True, "orbit": True, "wide": True,
                "victim": True, "placement": "end", "frequency": 1.0},
        key="same-demo",
    )
    plan = Plan("match.dem", "de_test", 64, Player("111", "Player"), [])
    job = hlae.build_job(plan, [], tmp_path, hlae.RecordSettings(), extra_shots=shots)
    assert {c["cam"] for c in job["clips"]} == {"pov"}
    victim = next(c for c in job["clips"] if c["steamid"] == "333")
    assert victim["start"] < victim["death"] == victim["focus"] < victim["end"]


def test_camera_progress_is_visible_without_treating_shots_as_rounds():
    from povforge.gui.server import Job
    job = Job()
    job._take("Camera recording 1/2: 3 extra shots (one CS2 session).")
    assert job.snapshot()["stage"] == "record"
    job._take("Recorded shot_follow_abcdef (2/3)")
    assert job.snapshot()["step"] == [2, 3]
    assert job.snapshot()["recorded"] == []
    job._take("Camera editing 1/4")
    assert job.snapshot()["stage"] == "cut"
    assert job.snapshot()["step"] == [1, 4]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs FFmpeg")
def test_all_main_moments_precede_every_victim_replay_in_selected_kill_order(tmp_path, monkeypatch):
    """Only game capture is substituted; plan, replay rendering and joining are real."""
    from povforge import hlae
    from povforge.media import probe
    cfg, items, windows, contexts = _sources(tmp_path)
    cfg.record.width, cfg.record.height, cfg.record.fps = 96, 54, 20
    cfg.compose.ffmpeg = shutil.which("ffmpeg")
    cfg.compose.preset = "ultrafast"
    cfg.upload.enabled = False

    def video(path, seconds, color):
        subprocess.run([cfg.compose.ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
                        f"color=c={color}:s=96x54:r=20", "-f", "lavfi", "-i",
                        "sine=frequency=440:sample_rate=48000", "-t", str(seconds),
                        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", str(path)], check=True)

    for it in items:
        key = (it.demo, it.steamid, it.round)
        job, _ = contexts[key]
        clip = windows[key][0][0]
        windows[key] = [(clip, 1.0, 3.0, [1.0, 1.5] if it.steamid == "11" else [1.5])]
        victims = [[1192, "44"], [1160, "33"]] if it.steamid == "11" else [[1192, "55"]]
        (job / "victims.json").write_text(json.dumps(victims), encoding="utf-8")
        video(clip, 4, "red" if it.steamid == "11" else "green")
    items.reverse()  # The selected main-reel order, not source-directory order, wins.
    captured = []

    def record(plan, job, settings, ffmpeg, *, extra_shots, shots_only):
        assert shots_only
        captured.extend((s["focus"], s["steamid"]) for s in extra_shots)
        paths, starts = [], hlae.actual_starts(job)
        for s in extra_shots:
            assert s["cam"] == "pov" and s["start"] < s["death"] == s["focus"] < s["end"]
            path = job / "shots" / (s["id"] + ".mp4")
            path.parent.mkdir(exist_ok=True)
            video(path, (s["end"] - s["start"]) / 64 + .2,
                  {"55": "blue", "33": "yellow", "44": "magenta"}[s["steamid"]])
            starts[s["id"]] = s["start"]
            paths.append(path)
        (job / "recorded.json").write_text(json.dumps(starts), encoding="utf-8")
        return paths

    monkeypatch.setattr(hlae, "record", record)
    fx = effects.normalize({"camera": {"mode": "pov", "victim": True, "placement": "end", "frequency": 0}})
    order = reel._camera_order(cfg, "Ending Replays", items, windows, contexts, fx)
    assert order[:2] == [windows[(i.demo, i.steamid, i.round)][0] for i in items]
    assert len(order) == 5
    assert captured == [(1192, "55"), (1160, "33"), (1192, "44")]
    assert all(w[3] == [] for w in order[2:])
    final = reel._plain_join(cfg, "Ending Replays", order)
    # Two 2s mains, then three replays each from the moment start (tick 1096) to
    # its end (1224): up to 3s before the death and up to 1s after it.
    assert probe(final, cfg.compose.ffmpeg).duration == pytest.approx(10.0, abs=.12)
    for when, expected in [(0.5, (0, 128, 0)), (2.5, (255, 0, 0)),
                           (5.0, (0, 0, 255)), (7.0, (255, 255, 0)), (9.0, (255, 0, 255))]:
        pixels = subprocess.run([cfg.compose.ffmpeg, "-v", "error", "-ss", str(when), "-i", str(final),
                                 "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                check=True, capture_output=True).stdout
        actual = tuple(sum(pixels[i::3]) / (len(pixels) / 3) for i in range(3))
        assert all(abs(a - e) < 15 for a, e in zip(actual, expected)), (when, actual)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="needs FFmpeg")
def test_reel_run_records_extra_shots_and_publishes_real_composite(tmp_path, monkeypatch):
    """Fake only the game; parsing saved metadata and all media work remain real."""
    from povforge import hlae, pipeline
    from povforge.media import probe
    cfg = Config(output_dir=tmp_path / "out")
    cfg.record.width, cfg.record.height, cfg.record.fps = 160, 90, 20
    cfg.compose.ffmpeg = shutil.which("ffmpeg")
    cfg.compose.preset = "ultrafast"
    cfg.upload.enabled = False
    demo = tmp_path / "match.dem"
    demo.write_bytes(b"fixture")
    job = pipeline.work_root(cfg) / "match__Player"
    hlae.prepare_quality_cache(job, cfg.record)
    clips = job / "clips"
    clips.mkdir(parents=True)
    plan = Plan(str(demo), "de_test", 64, Player("11", "Player"),
                [Segment(1, 640, 1024, "round_end")])
    (job / "plan.json").write_text(json.dumps(plan.to_dict()), encoding="utf-8")
    (job / "kills.json").write_text('[[896, false]]', encoding="utf-8")
    (job / "victims.json").write_text('[[896, "33"]]', encoding="utf-8")
    (job / "recorded.json").write_text('{"r01": 640.0}', encoding="utf-8")

    def video(path, seconds, color):
        subprocess.run([cfg.compose.ffmpeg, "-y", "-v", "error", "-f", "lavfi", "-i",
                        f"color=c={color}:s=160x90:r=20", "-f", "lavfi", "-i",
                        "sine=frequency=440:sample_rate=48000", "-t", str(seconds),
                        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", str(path)], check=True)

    video(clips / "clip_000.mp4", 6, "red")
    calls = []

    def record(plan, job, settings, ffmpeg, *, extra_shots, shots_only):
        calls.append(extra_shots)
        assert shots_only
        out, starts = [], hlae.actual_starts(job)
        for shot in extra_shots:
            path = job / "shots" / (shot["id"] + ".mp4")
            path.parent.mkdir(exist_ok=True)
            video(path, (shot["end"] - shot["start"]) / plan.tickrate + .1, "blue")
            starts[shot["id"]] = shot["start"]
            out.append(path)
        (job / "recorded.json").write_text(json.dumps(starts), encoding="utf-8")
        return out

    monkeypatch.setattr(hlae, "record", record)
    out = reel.run(cfg, "Camera Test", [reel.ReelItem(str(demo), "11", 1)],
                   fx={"camera": {"victim": True, "placement": "end"}})
    assert out.is_file()
    assert len(calls) == 1 and calls[0][0]["cam"] == "pov" and calls[0][0]["steamid"] == "33"
    # The default 3s tail retains all 6s of available main footage, plus a 4s replay
    # (3s before the victim's death and 1s after it).
    assert probe(out, cfg.compose.ffmpeg).duration == pytest.approx(10.0, abs=.1)
    from povforge.video_index import read
    events=read(out)
    assert next(e['at'] for e in events if e['kind']=='kill')==pytest.approx(4,abs=.05)
    assert next(e['at'] for e in events if e['kind']=='replay')==pytest.approx(6,abs=.05)
    assert not (pipeline.work_root(cfg) / "camera pieces" / "Camera Test").exists()
    # The main reel stays red; only the ending replay is blue.
    rgb = subprocess.run([cfg.compose.ffmpeg, "-v", "error", "-ss", "6.5", "-i", str(out),
                          "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    assert sum(rgb[2::3]) > 4 * sum(rgb[0::3])
