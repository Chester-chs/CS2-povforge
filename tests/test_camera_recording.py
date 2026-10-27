"""Camera recording contracts using real job files and a fake external game."""

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from povforge import hlae, pipeline, settings_guard, media
from povforge.model import Death, Plan, Player, Segment


def plan_at(tmp_path):
    demo = tmp_path / "match.dem"
    demo.write_bytes(b"demo")
    return Plan(str(demo), "de_test", 64.0, Player("76561198000000001", "Player"),
                [Segment(1, 1000, 1200, "round_end")])


def shot():
    return dict(id="shot_victim", start=1020, end=1100, steamid="76561198000000001",
                cam="pov", focus=1060)


def test_job_includes_extra_camera_clips_in_one_session(tmp_path):
    plan = plan_at(tmp_path)
    job = hlae.build_job(plan, plan.segments, tmp_path / "raw", hlae.RecordSettings(),
                         extra_shots=[shot()])
    assert job["clips"] == [
        {"id": "r01", "start": 1000, "end": 1200},
        {"id": "shot_victim", "start": 1020, "end": 1100, "steamid": "76561198000000001",
         "cam": "pov", "focus": 1060},
    ]










@pytest.mark.parametrize("changes", [
    {"id": "../outside"}, {"id": "A/B"}, {"id": "r01"}, {"id": "CON"},
    {"start": 1100, "end": 1020}, {"cam": "bad"}, {"steamid": "bad; quit"},
])
def test_invalid_shots_are_rejected_before_recording(tmp_path, changes):
    plan = plan_at(tmp_path)
    item = shot()
    item.update(changes)
    with pytest.raises(ValueError):
        hlae.record(plan, tmp_path / "job", hlae.RecordSettings(), extra_shots=[item], shots_only=True)


def fake_game(tmp_path, monkeypatch, *, fail_setup=False, cancel=False, end_reason="end_tick"):
    """Only replace the external HLAE/game boundary; retain files and settings guard."""
    steam = tmp_path / "steam"
    user = steam / "userdata" / "123" / "730" / "local" / "cfg"
    user.mkdir(parents=True)
    settings = user / "cs2_user_convars.vcfg"
    settings.write_bytes(b"original settings")
    cs2 = tmp_path / "game" / "bin" / "win64" / "cs2.exe"
    cs2.parent.mkdir(parents=True)
    cs2.write_bytes(b"fake")
    csgo = tmp_path / "game" / "csgo"
    (csgo / "cfg").mkdir(parents=True)
    cfg = csgo / "cfg" / "povforge_job.cfg"
    cfg.write_bytes(b"existing cfg")
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path / "state"))
    monkeypatch.setattr(hlae, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(hlae, "find_hlae", lambda s: tmp_path / "HLAE.exe")
    monkeypatch.setattr(hlae, "find_cs2", lambda s: cs2)
    monkeypatch.setattr(hlae, "_steam_dir", lambda: steam)
    monkeypatch.setattr(hlae.time, "sleep", lambda _: None)
    state = {"launched": 0, "checks": 0, "job": None, "produce_takes": True}

    def ensure(*_):
        if fail_setup:
            settings.write_bytes(b"changed during setup")
            raise RuntimeError("setup failed")

    monkeypatch.setattr(hlae, "ensure_ffmpeg_ini", ensure)

    def processes():
        if not state["launched"]:
            return set()
        state["checks"] += 1
        return {"cs2.exe"} if state["checks"] <= 2 else set()

    monkeypatch.setattr(hlae, "running_processes", processes)

    def launch(cmd, **kwargs):
        assert "-customLoader" in cmd
        state["launched"] += 1
        director = Path(cfg.read_text(encoding="utf-8").split('"')[1])
        text = director.read_text(encoding="utf-8")
        job = json.loads(text.split("const JOB = ", 1)[1].split(";\n", 1)[0])
        state["job"] = job
        settings.write_bytes(b"changed by cs2")
        (user / "new.vcfg").write_bytes(b"new")
        if cancel:
            raise KeyboardInterrupt()
        logs = []
        for clip in job["clips"]:
            if not state["produce_takes"]:
                logs.append(f"[povforge] ERROR could not lock camera for clip {clip['id']}, skipping it")
                continue
            take = Path(job["outDir"]) / clip["id"] / "take0000"
            take.mkdir(parents=True, exist_ok=True)
            (take / "video.mp4").write_bytes(clip["id"].encode())
            logs += [f"[povforge] START {clip['id']} tick={clip['start'] + 0.5}",
                     f"[povforge] END {clip['id']} tick={clip['end']}.0 why={end_reason}"]
        (csgo / "console.log").write_text("\n".join(logs), encoding="utf-8")
        return SimpleNamespace()

    monkeypatch.setattr(hlae.subprocess, "Popen", launch)
    monkeypatch.setattr(hlae.subprocess, "run", lambda *_a, **_k: SimpleNamespace(returncode=0))
    monkeypatch.setattr(hlae, "mux_take", lambda take, out, ffmpeg, s=None: out.write_bytes((take / "video.mp4").read_bytes()))
    monkeypatch.setattr(media, "probe", lambda *_a, **_k: media.VideoInfo(1920, 1080, 200 / 64, 188, 60))
    return state, settings, user, cfg


def test_shots_only_records_and_caches_without_recording_regular_clips(tmp_path, monkeypatch):
    plan = plan_at(tmp_path)
    state, settings, user, cfg = fake_game(tmp_path, monkeypatch)
    job = tmp_path / "job"
    paths = hlae.record(plan, job, hlae.RecordSettings(), extra_shots=[shot()], shots_only=True)
    assert paths == [job / "shots" / "shot_victim.mp4"]
    assert paths[0].read_bytes() == b"shot_victim"
    assert [c["id"] for c in state["job"]["clips"]] == ["shot_victim"]
    assert not (job / "clips" / "clip_000.mp4").exists()
    assert hlae.actual_starts(job)["shot_victim"] == 1020.5
    assert settings.read_bytes() == b"original settings"
    assert cfg.read_bytes() == b"existing cfg"
    assert not (user / "new.vcfg").exists()
    assert not settings_guard.pending()
    hlae.record(plan, job, hlae.RecordSettings(), extra_shots=[shot()], shots_only=True)
    assert state["launched"] == 1


def test_changed_shot_signature_cannot_reuse_old_video(tmp_path, monkeypatch):
    plan = plan_at(tmp_path)
    state, *_ = fake_game(tmp_path, monkeypatch)
    job = tmp_path / "job"
    hlae.record(plan, job, hlae.RecordSettings(), extra_shots=[shot()], shots_only=True)
    state["checks"] = 0
    state["launched"] = 0
    changed = shot()
    changed["start"] = 1040
    hlae.record(plan, job, hlae.RecordSettings(), extra_shots=[changed], shots_only=True)
    assert state["launched"] == 1
    assert hlae.actual_starts(job)["shot_victim"] == 1040.5


def test_old_mux_version_requires_shot_rerecording(tmp_path, monkeypatch):
    plan = plan_at(tmp_path)
    state, *_ = fake_game(tmp_path, monkeypatch)
    job = tmp_path / "job"
    with monkeypatch.context() as old:
        old.setattr(hlae, "_MUX_VERSION", 1, raising=False)
        hlae.record(plan, job, hlae.RecordSettings(), extra_shots=[shot()], shots_only=True)
    manifest = job / "shots" / "manifest.json"
    old_signature = json.loads(manifest.read_text(encoding="utf-8"))["shot_victim"]["signature"]
    state["checks"] = 0
    state["launched"] = 0

    hlae.record(plan, job, hlae.RecordSettings(), extra_shots=[shot()], shots_only=True)

    assert state["launched"] == 1
    assert json.loads(manifest.read_text(encoding="utf-8"))["shot_victim"]["signature"] != old_signature


@pytest.mark.parametrize("failure", ["setup", "cancel"])
def test_settings_restored_for_setup_failure_and_cancellation(tmp_path, monkeypatch, failure):
    plan = plan_at(tmp_path)
    _, settings, user, cfg = fake_game(tmp_path, monkeypatch, fail_setup=failure == "setup",
                                     cancel=failure == "cancel")
    error = RuntimeError if failure == "setup" else KeyboardInterrupt
    with pytest.raises(error):
        hlae.record(plan, tmp_path / "job", hlae.RecordSettings(), extra_shots=[shot()], shots_only=True)
    assert settings.read_bytes() == b"original settings"
    assert cfg.read_bytes() == b"existing cfg"
    assert not (user / "new.vcfg").exists()
    assert not settings_guard.pending()


def test_old_job_reads_and_caches_victims_from_its_demo(tmp_path, monkeypatch):
    plan = plan_at(tmp_path)
    job = tmp_path / "job"
    job.mkdir()
    (job / "plan.json").write_text(json.dumps(plan.to_dict()), encoding="utf-8")
    deaths = [
        Death(1050, "111", plan.player.steamid, "ak47"),
        Death(1070, plan.player.steamid, plan.player.steamid, "world"),
        Death(1090, "222", "333", "ak47"),
    ]
    monkeypatch.setattr(pipeline, "load_demo", lambda p: SimpleNamespace(deaths=deaths))
    assert pipeline.load_victims(job) == [(1050, "111")]
    monkeypatch.setattr(pipeline, "load_demo", lambda p: pytest.fail("cache should avoid reparsing"))
    assert pipeline.load_victims(job) == [(1050, "111")]


def test_failed_camera_in_regular_clip_is_not_published_or_reused(tmp_path, monkeypatch):
    plan = plan_at(tmp_path)
    state, *_ = fake_game(tmp_path, monkeypatch, end_reason="camera_error")
    job = tmp_path / "job"
    with pytest.raises(RuntimeError, match="not recorded"):
        hlae.record(plan, job, hlae.RecordSettings())
    assert not (job / "clips" / "clip_000.mp4").exists()
    state["checks"] = 0
    state["launched"] = 0
    with pytest.raises(RuntimeError, match="not recorded"):
        hlae.record(plan, job, hlae.RecordSettings())
    assert state["launched"] == 1
    assert not (job / "clips" / "clip_000.mp4").exists()


@pytest.mark.parametrize("shots_only", [False, True])
def test_failed_take_is_never_revived_after_an_empty_retry_log(tmp_path, monkeypatch, shots_only):
    plan = plan_at(tmp_path)
    state, *_ = fake_game(tmp_path, monkeypatch, end_reason="camera_error")
    job = tmp_path / "job"
    args = {"extra_shots": [shot()], "shots_only": True} if shots_only else {}
    output = job / "shots" / "shot_victim.mp4" if shots_only else job / "clips" / "clip_000.mp4"
    with pytest.raises(RuntimeError, match="not recorded"):
        hlae.record(plan, job, hlae.RecordSettings(), **args)
    state["produce_takes"] = False
    # Both retries only emit the error message, without a new START/END or raw take.
    # The second such retry must not revive the partial video from the first attempt.
    for _ in range(2):
        state["checks"] = 0
        state["launched"] = 0
        with pytest.raises(RuntimeError, match="before recording began"):
            hlae.record(plan, job, hlae.RecordSettings(), **args)
        assert state["launched"] == 1
        assert not output.exists()


@pytest.mark.parametrize("restore_result", ["raises", "pending"])
def test_recording_cannot_succeed_until_settings_are_restored(tmp_path, monkeypatch, restore_result):
    plan = plan_at(tmp_path)
    fake_game(tmp_path, monkeypatch)

    def restore():
        if restore_result == "raises":
            raise OSError("settings are locked")
        return 0  # no files restored; the real pending backup remains

    monkeypatch.setattr(settings_guard, "restore", restore)
    with pytest.raises(RuntimeError, match="restore-settings"):
        hlae.record(plan, tmp_path / "job", hlae.RecordSettings(), extra_shots=[shot()], shots_only=True)
    assert settings_guard.pending()
    assert not (tmp_path / "job" / "shots" / "shot_victim.mp4").exists()


def test_settings_cleanup_refuses_success_while_cs2_is_open(tmp_path, monkeypatch):
    monkeypatch.setattr(hlae, "running_processes", lambda: {"cs2.exe"})
    monkeypatch.setattr(hlae.time, "sleep", lambda _: None)
    with pytest.raises(RuntimeError, match="restore-settings"):
        hlae._put_settings_back(True)


@pytest.mark.parametrize("damage", ["missing_end", "corrupt", "short", "probe_error"])
def test_interrupted_raw_take_is_discarded_and_rerecorded(tmp_path, monkeypatch, damage):
    plan = plan_at(tmp_path)
    state, *_ = fake_game(tmp_path, monkeypatch)
    job = tmp_path / "job"
    take = job / "raw" / "r01" / "take0000"
    take.mkdir(parents=True)
    (take / "video.mp4").write_bytes(b"old interrupted recording")
    log = "[povforge] START r01 tick=1000.5\n"
    if damage != "missing_end":
        log += "[povforge] END r01 tick=1200.0 why=end_tick\n"
    (job / "cs2_console.log").write_text(log)
    (job / "recorded.json").write_text(json.dumps({"r01": 1000.5}))

    def probe(path, *args):
        if path.read_bytes().startswith(b"old"):
            if damage == "corrupt":
                raise ValueError("Unreadable MP4")
            if damage == "probe_error":
                raise subprocess.CalledProcessError(1, ['ffprobe', str(path)], stderr='moov atom not found')
            if damage == "short":
                return media.VideoInfo(1920, 1080, 0.25, 15, 60)
        return media.VideoInfo(1920, 1080, 200 / 64, 188, 60)

    def mux(take, out, ffmpeg, s=None):
        data = (take / "video.mp4").read_bytes()
        out.write_bytes(data)

    monkeypatch.setattr(media, "probe", probe)
    monkeypatch.setattr(hlae, "mux_take", mux)
    paths = hlae.record(plan, job, hlae.RecordSettings())
    assert state["launched"] == 1
    assert paths[0].read_bytes() == b"r01"


def test_complete_ordinary_raw_take_can_resume_without_launch(tmp_path, monkeypatch):
    plan = plan_at(tmp_path)
    state, *_ = fake_game(tmp_path, monkeypatch)
    job = tmp_path / "job"
    take = job / "raw" / "r01" / "take0000"
    take.mkdir(parents=True)
    (take / "video.mp4").write_bytes(b"complete recording")
    (job / "cs2_console.log").write_text(
        "[povforge] START r01 tick=1000.5\n[povforge] END r01 tick=1200.0 why=end_tick\n")
    (job / "recorded.json").write_text(json.dumps({"r01": 1000.5}))
    paths = hlae.record(plan, job, hlae.RecordSettings())
    assert state["launched"] == 0
    assert paths[0].read_bytes() == b"complete recording"


@pytest.mark.parametrize('failure', ['permission', 'ffmpeg'])
def test_output_permission_error_preserves_complete_raw_take(tmp_path, monkeypatch, failure):
    plan = plan_at(tmp_path)
    state, *_ = fake_game(tmp_path, monkeypatch)
    job = tmp_path / 'job'
    take = job / 'raw/r01/take0000'
    take.mkdir(parents=True)
    video = take / 'video.mp4'
    video.write_bytes(b'complete recording')
    (job / 'cs2_console.log').write_text(
        '[povforge] START r01 tick=1000.5\n[povforge] END r01 tick=1200.0 why=end_tick\n')
    def denied(*args):
        if failure == 'ffmpeg':
            raise subprocess.CalledProcessError(1, ['ffmpeg'], stderr='Error opening output file: Permission denied')
        raise PermissionError('output directory is read-only')
    monkeypatch.setattr(hlae, 'mux_take', denied)
    with pytest.raises(PermissionError if failure == 'permission' else subprocess.CalledProcessError):
        hlae.record(plan, job, hlae.RecordSettings())
    assert video.read_bytes() == b'complete recording'
    assert state['launched'] == 0


def test_victim_take_that_left_after_death_is_kept_with_its_cut_tick(tmp_path, monkeypatch):
    """The director ends a victim take when CS2 moves the camera off the dead
    victim; the shot is usable, and where the camera left is remembered so the
    replay never shows the other player."""
    plan = plan_at(tmp_path)
    fake_game(tmp_path, monkeypatch, end_reason="after_death")
    job = tmp_path / "job"
    item = {**shot(), "death": 1060}
    paths = hlae.record(plan, job, hlae.RecordSettings(), extra_shots=[item], shots_only=True)
    assert paths[0].is_file()
    assert hlae.shot_cuts(job) == {"shot_victim": 1100.0}


def test_shot_cuts_ignore_damaged_files(tmp_path):
    (tmp_path / "shot-cuts.json").write_text("{broken", encoding="utf-8")
    assert hlae.shot_cuts(tmp_path) == {}
    (tmp_path / "shot-cuts.json").write_text('{"a": 12.5, "b": "x", "c": null}', encoding="utf-8")
    assert hlae.shot_cuts(tmp_path) == {"a": 12.5}
