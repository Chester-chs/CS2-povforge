"""Recording backend: CS2 Video Generator (CSVG).

CSVG (https://github.com/CS2OpenDev/CS2VideoGenerator, GPL-3.0) drives CS2
through its own engine plugin and renders demo ranges offline, frame-exact,
locked to a chosen player. We don't include any of its code: we write its
documented "compilation" JSON and run its ``csvg`` command-line tool.

Install it separately (see README) and make sure ``csvg`` and ``ffmpeg`` are
on PATH, or set the paths in the config.

Note: CSVG launches CS2 with -insecure (VAC off) for the recording session and
restores your settings afterwards. Never join online servers while it runs.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .model import Plan


@dataclass
class RecordSettings:
    width: int = 1920
    height: int = 1080
    fps: int = 60
    # Game HUD on, no X-ray: a fair first-person view.
    clip_options: str = "TrueViewEnabled, HudEnabled, ShowAssistsInFeed"
    executable: str = "csvg"


def clip_path(clips_dir: Path, index: int) -> Path:
    return clips_dir / f"clip_{index:03d}.mp4"


def build_compilation(plan: Plan, clips_dir: Path, s: RecordSettings) -> dict:
    demo = str(Path(plan.demo_path).resolve()).replace("\\", "/")
    return {
        "settings": {
            "outputDirectory": str(clips_dir.resolve()).replace("\\", "/"),
            "baseFileName": "clip",
            "containerFormat": "mp4",
            "frameRate": s.fps,
            "width": s.width,
            "height": s.height,
            "captureAudio": True,
            "concatenateClips": False,
        },
        "clips": [
            {
                "demoFilePath": demo,
                "startTick": seg.start_tick,
                "endTick": seg.end_tick,
                "playerNameToSpectate": plan.player.name,
                "playerSteamId": int(plan.player.steamid),
                "clipOptions": s.clip_options,
            }
            for seg in plan.segments
        ],
    }


def write_compilation(plan: Plan, job_dir: Path, s: RecordSettings) -> Path:
    clips_dir = job_dir / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    path = job_dir / "compilation.json"
    path.write_text(json.dumps(build_compilation(plan, clips_dir, s), indent=2), encoding="utf-8")
    return path


def record(plan: Plan, job_dir: Path, s: RecordSettings) -> list[Path]:
    """Run CSVG for every segment not recorded yet. Returns the clip paths."""
    clips_dir = job_dir / "clips"
    expected = [clip_path(clips_dir, i) for i in range(len(plan.segments))]
    if all(p.exists() for p in expected):
        return expected
    comp = write_compilation(plan, job_dir, s)
    try:
        subprocess.run([s.executable, "generate", "--file", str(comp)], check=True)
    except FileNotFoundError as e:
        raise SystemExit(
            f"'{s.executable}' not found. Install CS2 Video Generator and add it to PATH "
            "(see README), or set [record] executable in the config."
        ) from e
    missing = [p.name for p in expected if not p.exists()]
    if missing:
        raise RuntimeError(f"CSVG finished but these clips are missing: {', '.join(missing)}")
    return expected
