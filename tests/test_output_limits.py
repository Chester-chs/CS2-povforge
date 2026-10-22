import json
import shutil
import subprocess

import pytest

from povforge.config import load_config
from povforge.gui import server
from povforge.hlae import RecordSettings


def test_legacy_config_is_capped(tmp_path):
    path = tmp_path / "old.toml"
    path.write_text("[record]\nwidth=3840\nheight=2160\nfps=120\n[upload]\nupscale=2160\n")
    cfg = load_config(path)
    assert (cfg.record.width, cfg.record.height, cfg.record.fps) == (1920, 1080, 60)
    assert cfg.upload.upscale == 0


def test_legacy_preferences_cannot_enable_4k(tmp_path, monkeypatch):
    monkeypatch.setenv("POVFORGE_STATE", str(tmp_path))
    server.app_dir().mkdir()
    (server.app_dir() / "app.json").write_text(json.dumps({
        "record_res": "2160", "record_fps": 120, "upload_4k": True,
    }))
    prefs = server.load_prefs()
    assert prefs["record_res"] == "1080"
    assert prefs["record_fps"] == 60
    assert "upload_4k" not in prefs


def test_record_settings_cap_preserves_aspect_and_small_outputs():
    wide = RecordSettings(width=3440, height=1440, fps=120)
    wide.limit_output()
    assert wide.width == 1920 and wide.height == 802 and wide.fps == 60
    small = RecordSettings(width=640, height=360, fps=30)
    small.limit_output()
    assert (small.width, small.height, small.fps) == (640, 360, 30)


def test_auto_resolution_fits_a_small_screen():
    assert server.record_size({"record_res": "auto"}, (1366, 768)) == (1364, 768)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_plain_cut_caps_cached_high_resolution_and_frame_rate(tmp_path):
    from povforge.compose import ComposeSettings
    from povforge.extras import _cut
    from povforge.media import probe

    source, out = tmp_path / "cached.mp4", tmp_path / "out.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i",
                    "color=blue:s=2560x1440:r=120:d=0.2", "-c:v", "libx264",
                    "-preset", "ultrafast", str(source)], check=True)
    _cut(source, 0, 0.2, out, ComposeSettings(preset="ultrafast"))
    info = probe(out)
    assert (info.width, info.height) == (1920, 1080)
    assert info.fps <= 60


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
def test_composition_rebuilds_an_oversized_cached_part(tmp_path):
    from povforge.compose import ComposeSettings, compose
    from povforge.media import probe
    from povforge.model import Plan, Player, Segment
    job = tmp_path / "job"
    (job / "parts").mkdir(parents=True)
    source, old = job / "source.mp4", job / "parts/part_000.mp4"
    for path, size, fps in ((source, "320x180", 30), (old, "2560x1440", 120)):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i",
                        f"color=blue:s={size}:r={fps}:d=0.2", "-c:v", "libx264",
                        "-preset", "ultrafast", str(path)], check=True)
    plan = Plan("demo.dem", "de_dust2", 64, Player("1", "test"), [Segment(1, 0, 13, "round_end")])
    out = compose(plan, job, [source], [{}], 120, ComposeSettings(preset="ultrafast"), size=(3840, 2160))
    info = probe(out)
    assert (info.width, info.height, info.fps) == (1920, 1080, 60)
