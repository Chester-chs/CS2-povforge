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


def test_camera_selection_normalization_and_cross_platform_event_identity():
    key = camera.event_key('C:\\Demos\\Match.dem.zst', '11', 1280, '33')
    assert key == camera.event_key('c:/demos/match.dem.zst', '11', 1280, '33')
    choice = camera.normalize_camera({'victim': True, 'placement': 'after_kill', 'selected': [key, key, 3, {}]})
    assert choice['selected'] == [key]
    assert choice['placement'] == 'after_kill'
    assert camera.normalize_camera({})['selected'] is None
    assert camera.normalize_camera({'selected': []})['selected'] == []


def test_selected_replays_are_inline_and_keep_explicit_duel_order(tmp_path, monkeypatch):
    from povforge import hlae
    cfg, items, windows, contexts = _sources(tmp_path)
    spans = [(key, value[0]) for key, value in windows.items()]
    spans.reverse()  # Event sequence may differ from grouping by selected player.
    selected = camera.event_key(items[0].demo, '11', 1280, '33')
    captured = []

    def record(plan, job, settings, ffmpeg, *, extra_shots, shots_only):
        captured.extend(extra_shots)
        return [job / (s['id'] + '.mp4') for s in extra_shots]

    monkeypatch.setattr(hlae, 'record', record)
    monkeypatch.setattr(camera, 'render_replay', lambda **kw: (kw['out'], 0., 1., []))
    order = reel._camera_order(cfg, 'Inline', items, windows, contexts,
                              {'camera': {'victim': True, 'selected': [selected]}}, ordered_spans=spans)
    assert len(captured) == 1
    assert order[0] == spans[0][1]
    assert order[1][0] == spans[1][1][0]
    assert order[2][0].name.startswith('replay_')
    assert order[3][0] == order[1][0]
    assert order[1][2] == order[3][1]
    assert order[1][2] == pytest.approx(3.875 + 1 / cfg.record.fps, abs=1/cfg.record.fps)


def test_event_modes_strip_hidden_styles_but_keep_audio_and_victim_choices():
    fx = effects.for_event_reel({'transition': 'flash', 'intro': 'title', 'pace': 'tight',
                                'kill_slowmo': True, 'music': 'song.mp3', 'game_audio': 'low',
                                'camera': {'victim': True, 'selected': []}})
    assert fx['transition'] == 'cut' and fx['intro'] == 'none'
    assert fx['pace'] == 'normal' and fx['kill_slowmo'] is False
    assert fx['music'] == 'song.mp3' and fx['game_audio'] == 'low'
    assert fx['camera']['victim'] is True and fx['camera']['selected'] == []
