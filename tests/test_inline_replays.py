"""Inline victim replays preserve the source timeline and explicit user choices."""
from pathlib import Path

import pytest

from povforge import camera, effects, reel
from test_reel_cameras import _sources


def test_inline_replays_preserve_every_main_frame_and_rebase_kills():
    span = (Path('main.mp4'), 1., 5., [1., 2.])
    replay = (Path('victim.mp4'), 0., 1., [])
    order = camera.interleave_replays(span, [(2.05, replay), (3.05, replay)], 20)
    assert order == [(span[0], 1., 2.05, [1.]), replay,
                     (span[0], 2.05, 3.05, [pytest.approx(.95)]), replay,
                     (span[0], 3.05, 5., [])]
    mains = [s for s in order if s[0] == span[0]]
    assert sum(s[2] - s[1] for s in mains) == pytest.approx(4.)
    assert all(a[2] == b[1] for a, b in zip(mains, mains[1:]))
    assert camera.interleave_replays(span, [], 20) == [span]


def test_simultaneous_victims_and_final_frame_do_not_duplicate_main_footage():
    span = (Path('main.mp4'), 0., 2., [1., 1.99])
    replay = (Path('victim.mp4'), 0., 1., [])
    order = camera.interleave_replays(span, [(1.05, replay), (1.05, replay), (2., replay)], 20)
    assert len(order) == 5
    assert order[1:3] == [replay, replay]
    assert order[-1] == replay
    assert sum(s[2]-s[1] for s in order if s[0] == span[0]) == 2.


def test_victim_replay_is_one_switch_and_legacy_selection_is_dropped():
    # An old per-kill list (an empty one meant "none") must not limit the switch.
    choice = camera.normalize_camera({'victim': True, 'placement': 'after_kill', 'selected': []})
    assert choice == {'mode': 'pov', 'victim': True, 'placement': 'after_kill', 'durations': {'before': 3.0, 'after': 1.0}}
    assert 'selected' not in camera.normalize_camera({})


@pytest.mark.parametrize('legacy', [None, [], ['forged-event']])
def test_switch_on_replays_every_kill_inline_in_explicit_order(tmp_path, monkeypatch, legacy):
    from dataclasses import replace
    from povforge import hlae
    cfg, items, windows, contexts = _sources(tmp_path)
    # Compressed sources still map onto the unpacked plan.
    old_windows, old_contexts = windows, contexts
    items = [replace(it, demo=it.demo + '.zst') for it in items]
    windows = {(it.demo,it.steamid,it.round): old_windows[(it.demo[:-4],it.steamid,it.round)] for it in items}
    contexts = {(it.demo,it.steamid,it.round): old_contexts[(it.demo[:-4],it.steamid,it.round)] for it in items}
    spans = [(key, value[0]) for key, value in windows.items()]
    spans.reverse()  # Event sequence may differ from grouping by player.
    captured = []

    def record(plan, job, settings, ffmpeg, *, extra_shots, shots_only):
        captured.extend(extra_shots)
        return [job / (s['id'] + '.mp4') for s in extra_shots]

    monkeypatch.setattr(hlae, 'record', record)
    monkeypatch.setattr(camera, 'render_replay', lambda **kw: (kw['out'], 0., 1., []))
    cam = {'victim': True} if legacy is None else {'victim': True, 'selected': legacy}
    order = reel._camera_order(cfg, 'Inline', items, windows, contexts, {'camera': cam}, ordered_spans=spans)
    assert len(captured) == 2  # both players' kills, nothing to pick
    for n, (_, span) in enumerate(spans):
        main, replay, rest = order[3 * n:3 * n + 3]
        assert main[0] == rest[0] == span[0]
        assert replay[0].name.startswith('replay_')
        assert main[2] == rest[1]
        assert main[2] == pytest.approx(3.875 + 1 / cfg.record.fps, abs=1/cfg.record.fps)


def test_switch_off_never_triggers_extra_recording(tmp_path, monkeypatch):
    from povforge import hlae
    cfg, items, windows, contexts = _sources(tmp_path)
    monkeypatch.setattr(hlae, 'record', lambda *a, **kw: pytest.fail('victim replays are off'))
    order = reel._camera_order(cfg, 'None', items, windows, contexts, {'camera': {'victim': False}})
    assert order == [windows[(it.demo,it.steamid,it.round)][0] for it in items]


def test_event_modes_strip_hidden_styles_but_keep_audio_and_victim_choices():
    fx = effects.for_event_reel({'transition': 'flash', 'intro': 'title', 'pace': 'tight',
                                'kill_slowmo': True, 'music': 'song.mp3', 'game_audio': 'low',
                                'camera': {'victim': True}})
    assert fx['transition'] == 'cut' and fx['intro'] == 'none'
    assert fx['pace'] == 'normal' and fx['kill_slowmo'] is False
    assert fx['music'] == 'song.mp3' and fx['game_audio'] == 'low'
    assert fx['camera']['victim'] is True


@pytest.mark.parametrize('mode', ['kill_events', 'kills_deaths', 'duel'])
def test_event_pipeline_routes_replays_with_encounter_order_and_no_hidden_styles(tmp_path, monkeypatch, mode):
    from types import SimpleNamespace
    from povforge import pipeline, reel_events
    from povforge.model import Plan, Player, Segment
    from povforge.config import Config
    from test_event_reels import sample
    cfg = Config(output_dir=tmp_path/'output')
    jobs = {}
    for sid in ('a', 'b'):
        job = tmp_path/sid
        (job/'clips').mkdir(parents=True)
        (job/'clips/clip_000.mp4').write_bytes(b'fixture')
        jobs[sid] = job
    monkeypatch.setattr(reel_events, 'load_sources', lambda *args: {'test.dem': (sample(), {1:{'a':2,'b':3}})})
    monkeypatch.setattr(pipeline, 'whole_match_job', lambda cfg,demo,sid: jobs[sid])
    monkeypatch.setattr(pipeline, 'load_plan', lambda job: Plan('test.dem','de_test',10,Player(job.name,job.name),[Segment(1,0,200,'round_end')]))
    monkeypatch.setattr(reel_events, 'probe', lambda *args: SimpleNamespace(duration=20))
    routed = []

    def order(cfg, title, items, windows, contexts, fx, placeholder, *, ordered_spans):
        routed.append(ordered_spans)
        assert fx['camera']['victim'] is (mode != 'duel')
        assert fx['transition'] == 'cut' and fx['pace'] == 'normal'
        assert all(key in contexts for key, _ in ordered_spans)
        return [span for _, span in ordered_spans]

    monkeypatch.setattr(reel, '_camera_order', order)
    monkeypatch.setattr(reel, '_plain_join', lambda cfg,title,order: order)
    def compose(cfg, title, order, fx):
        assert fx['transition'] == 'cut' and fx['intro'] == 'none' and not fx['kill_slowmo']
        return order
    monkeypatch.setattr(reel, '_with_effects', compose)
    result = reel.run(cfg, 'Events', [reel.ReelItem('test.dem','a',1,mode,'b')],
                      fx={'transition':'flash','pace':'tight','camera':{'victim':True}})
    assert len(routed) == 1 and result
    if mode == 'duel':
        assert [key[1] for key,_ in routed[0]] == ['a','b']


def test_inline_assembly_uses_real_replay_video_and_main_timeline_audio(tmp_path, monkeypatch):
    import json
    import shutil
    import subprocess
    import numpy as np
    from povforge import hlae
    from povforge.media import probe
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        pytest.skip('FFmpeg required')
    cfg, items, windows, contexts = _sources(tmp_path)
    cfg.record.width, cfg.record.height, cfg.record.fps = 96, 54, 20
    cfg.compose.ffmpeg, cfg.compose.preset = ffmpeg, 'ultrafast'
    item = items[0]
    key = (item.demo, item.steamid, item.round)
    job, _ = contexts[key]
    clip = windows[key][0][0]
    windows[key] = [(clip, 1., 5., [1.5, 2.5])]
    (job / 'victims.json').write_text('[[1192,"33"],[1256,"44"]]')

    def video(path, color, seconds, tone):
        path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([ffmpeg, '-y', '-v', 'error', '-f', 'lavfi', '-i',
                        f'color={color}:s=96x54:r=20', '-f', 'lavfi', '-i',
                        f'sine=frequency={tone}:sample_rate=48000', '-t', str(seconds),
                        '-c:v', 'libx264', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
                        '-c:a', 'aac', str(path)], check=True)

    video(clip, 'red', 6, 440)

    def capture(plan, job, settings, ffmpeg, *, extra_shots, shots_only):
        starts, paths = hlae.actual_starts(job), []
        for s in extra_shots:
            path = job / 'shots' / (s['id'] + '.mp4')
            video(path, 'blue', (s['end']-s['start'])/64 + .2, 880)
            starts[s['id']] = s['start']
            paths.append(path)
        (job/'recorded.json').write_text(json.dumps(starts))
        return paths

    monkeypatch.setattr(hlae, 'record', capture)
    order = reel._camera_order(cfg, 'Inline media', [item], windows, contexts, {'camera': {'victim': True}})
    assert len(order) == 5
    mains = [s for s in order if s[0] == clip]
    assert sum(s[2]-s[1] for s in mains) == pytest.approx(4)
    final = reel._with_effects(cfg, 'Inline media', order, effects.normalize({'camera': {'victim': True}}))
    info = probe(final, ffmpeg)
    # 80 main frames plus two replays of 3 s before to 1 s after each death,
    # clamped to the moment: 1096-1256 (2.5 s, 50 frames) and 1096-1320 (3.5 s, 70).
    assert info.frames == 200
    assert info.duration == pytest.approx(10.0, abs=.1)
    for sec, blue in [(0.4, False), (2.5, True), (4.5, False), (6.0, True), (9.5, False)]:
        pixels = subprocess.run([ffmpeg, '-v', 'error', '-ss', str(sec), '-i', str(final),
                                 '-frames:v', '1', '-vf', 'scale=1:1', '-f', 'rawvideo',
                                 '-pix_fmt', 'rgb24', '-'], check=True, capture_output=True).stdout
        assert (pixels[2] > pixels[0]) == blue
    # Replay recordings contain 880 Hz; final replay sound must use source-time 440 Hz.
    audio = subprocess.run([ffmpeg, '-v', 'error', '-ss', '2.5', '-i', str(final),
                            '-t', '0.4', '-f', 'f32le', '-ac', '1', '-ar', '48000', '-'],
                           check=True, capture_output=True).stdout
    samples = np.frombuffer(audio, dtype='<f4')
    peak = np.argmax(abs(np.fft.rfft(samples))) * 48000 / len(samples)
    assert peak == pytest.approx(440, abs=5)
