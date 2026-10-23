"""Cleaning recording work preserves source files and the separate demo summary."""

import json

import pytest

from povforge import pipeline
from povforge.config import Config
from povforge.gui import server
from test_audit_plan_identity import fake_parser


def test_clean_work_keeps_demo_summary_and_final_video_but_rebuilds_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path / "state"))
    monkeypatch.setattr(server, "_inspect_cache", {})
    fake_parser(monkeypatch)
    cfg = Config(output_dir=tmp_path / "output")
    source = tmp_path / "match.dem"
    source.write_bytes(b"original demo")
    summary = {"map": "de_test", "rounds": 1}
    summary_file = server._inspection_file(server._inspection_key(source))
    summary_file.parent.mkdir(parents=True)
    summary_file.write_text(json.dumps(summary), encoding="utf-8")
    monkeypatch.setattr(server.subprocess, "run", lambda *args, **kwargs:
                        pytest.fail("The saved demo summary should not be parsed again"))

    parser = pipeline.load_demo
    reads = []

    def read_demo(path):
        reads.append(path)
        return parser(path)

    monkeypatch.setattr(pipeline, "load_demo", read_demo)
    first_plan, job = pipeline.make_plan(cfg, source, "111")
    cfg.output_dir.joinpath("finished.mp4").write_bytes(b"published video")
    assert pipeline.make_plan(cfg, source, "111")[0] == first_plan
    assert len(reads) == 1

    assert server.clean_work({"output": str(cfg.output_dir)}) > 0

    assert not pipeline.work_root(cfg).exists()
    assert source.read_bytes() == b"original demo"
    assert cfg.output_dir.joinpath("finished.mp4").read_bytes() == b"published video"
    assert json.loads(summary_file.read_text(encoding="utf-8")) == summary
    assert server.inspect_isolated(str(source), pipeline.work_root(cfg)) == summary
    rebuilt_plan, rebuilt_job = pipeline.make_plan(cfg, source, "111")
    assert rebuilt_plan == first_plan
    assert rebuilt_job == job
    assert len(reads) == 2
    assert (rebuilt_job / "plan.json").is_file()
    assert (rebuilt_job / "positions.pkl").is_file()
