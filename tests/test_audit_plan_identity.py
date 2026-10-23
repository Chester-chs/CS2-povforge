"""Recording caches must belong to their exact demo and player."""

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from povforge import pipeline
from povforge.config import Config
from povforge.model import Plan, Player, Segment


def fake_parser(monkeypatch):
    def demo(path):
        return SimpleNamespace(map_name="de_test", tickrate=64, last_tick=200,
                               players=[Player("111", "Same Name"), Player("222", "Same Name")],
                               deaths=[], rounds=[])
    monkeypatch.setattr(pipeline, "load_demo", demo)
    monkeypatch.setattr(pipeline, "load_ticks", lambda *_: (pd.DataFrame(columns=["steamid"]), pd.DataFrame()))
    monkeypatch.setattr(pipeline, "load_hud", lambda *_: pd.DataFrame())
    monkeypatch.setattr(pipeline, "load_utility", lambda *_: {})
    monkeypatch.setattr(pipeline, "load_scoreboard", lambda *_: [])
    monkeypatch.setattr(pipeline.highlights, "analyse", lambda *_: [])
    monkeypatch.setattr(pipeline, "plan_segments", lambda *_args, **_kwargs: [Segment(1, 64, 192, "round_end")])


@pytest.mark.parametrize("changed", ["directory", "player", "demo-revision", "plan-options"])
def test_different_source_cannot_reuse_previous_job_or_clips(tmp_path, monkeypatch, changed):
    fake_parser(monkeypatch)
    cfg = Config(output_dir=tmp_path / "output")
    demo = tmp_path / "match.dem"
    demo.write_bytes(b"first demo")
    _, first = pipeline.make_plan(cfg, demo, "111")
    (first / "clips").mkdir()
    original = first / "clips" / "clip_000.mp4"
    original.write_bytes(b"old player or match")
    player = "111"
    if changed == "directory":
        demo = tmp_path / "other" / "match.dem"
        demo.parent.mkdir()
        demo.write_bytes(b"different demo")
    elif changed == "player":
        player = "222"
    elif changed == "demo-revision":
        demo.write_bytes(b"new match with the same filename")
    else:
        cfg.plan.post_death_seconds += 1
    _, second = pipeline.make_plan(cfg, demo, player)
    assert second != first
    assert not (second / "clips" / "clip_000.mp4").exists()
    assert original.read_bytes() == b"old player or match"
    assert pipeline.make_plan(cfg, demo, player)[1] == second


def test_whole_match_lookup_rejects_same_filename_from_another_folder(tmp_path):
    cfg = Config(output_dir=tmp_path / "output")
    one, two = tmp_path / "one" / "match.dem", tmp_path / "two" / "match.dem"
    for demo in (one, two):
        demo.parent.mkdir()
        demo.write_bytes(b"demo")
    job = pipeline.job_dir_for(cfg, one, "Player")
    job.mkdir(parents=True)
    plan = Plan(str(one), "de_test", 64, Player("111", "Player"), [])
    (job / "plan.json").write_text(json.dumps(plan.to_dict()), encoding="utf-8")
    assert pipeline.whole_match_job(cfg, two, "111") is None
    assert pipeline.whole_match_job(cfg, one, "111") == job
    cfg.record.fps = 120
    assert pipeline.whole_match_job(cfg, one, "111") is None
