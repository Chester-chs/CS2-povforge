"""A failed encoder must not publish a broken reel beside completed videos."""

import subprocess
import errno
from types import SimpleNamespace
from pathlib import Path

import pytest

from povforge import effects, reel
from povforge.config import Config


@pytest.mark.parametrize("with_effects", [False, True])
def test_failed_reel_render_does_not_publish_partial_video(tmp_path, monkeypatch, with_effects):
    cfg = Config(output_dir=tmp_path / "output")
    order = [(tmp_path / "source.mp4", 0, 1, [])]
    cfg.output_dir.mkdir()
    keep = cfg.output_dir / "existing.mp4"
    keep.write_bytes(b"completed video")

    def fail_at_output(path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"incomplete encoder output")
        raise subprocess.CalledProcessError(1, "ffmpeg")

    if with_effects:
        monkeypatch.setattr(effects, "build", lambda moments, fx, out, *a, **kw: fail_at_output(out))
        render = lambda: reel._with_effects(cfg, "Test", order, effects.normalize({}))
    else:
        monkeypatch.setattr(reel, "_cut", lambda *a: None)
        monkeypatch.setattr(reel.subprocess, "run", lambda cmd, **kw: fail_at_output(cmd[-1]))
        render = lambda: reel._plain_join(cfg, "Test", order)
    with pytest.raises(subprocess.CalledProcessError):
        render()
    assert list(cfg.output_dir.glob("*.mp4")) == [keep]
    assert keep.read_bytes() == b"completed video"


@pytest.mark.parametrize("with_effects", [False, True])
def test_reel_publication_does_not_require_same_filesystem_as_work(tmp_path, monkeypatch, with_effects):
    cfg = Config(output_dir=tmp_path / "work-volume")
    cfg.video_dir = tmp_path / "video-volume"
    order = [(tmp_path / "source.mp4", 0, 1, [])]
    original = Path.replace

    def same_directory_only(path, target):
        if path.parent != Path(target).parent:
            raise OSError(errno.EXDEV, "cross-device rename")
        return original(path, target)

    monkeypatch.setattr(Path, "replace", same_directory_only)
    monkeypatch.setattr(reel.pipeline, "make_upload_copy", lambda *a: None)
    if with_effects:
        monkeypatch.setattr(effects, "build", lambda moments, fx, out, *a, **kw: Path(out).write_bytes(b"complete"))
        monkeypatch.setattr(reel, "probe", lambda *a: SimpleNamespace(duration=1))
        out = reel._with_effects(cfg, "Test", order, effects.normalize({}))
    else:
        monkeypatch.setattr(reel, "_cut", lambda *a: None)
        monkeypatch.setattr(reel.subprocess, "run", lambda cmd, **kw: Path(cmd[-1]).write_bytes(b"complete"))
        out = reel._plain_join(cfg, "Test", order)
    assert out.read_bytes() == b"complete"
