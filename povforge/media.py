"""Small helpers around ffprobe."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


def bounded_size(width: int, height: int) -> tuple[int, int]:
    """Fit within 1080p without stretching; H.264 requires even dimensions."""
    if width < 2 or height < 2:
        raise ValueError("Video dimensions must be at least 2 pixels.")
    scale = min(1.0, 1920 / width, 1080 / height)
    return max(2, int(width * scale) // 2 * 2), max(2, int(height * scale) // 2 * 2)


def bounded_fps(fps: float) -> float:
    import math
    if not math.isfinite(fps) or fps <= 0:
        raise ValueError("Frame rate must be positive and finite.")
    return min(fps, 60)


def ffprobe_for(ffmpeg: str) -> str:
    """ffprobe next to the configured ffmpeg ("ffmpeg" -> "ffprobe")."""
    p = Path(ffmpeg)
    if p.parent == Path("."):
        return "ffprobe"
    return str(p.with_name(p.name.lower().replace("ffmpeg", "ffprobe")))


@dataclass
class VideoInfo:
    width: int
    height: int
    duration: float
    frames: int
    fps: float = 0.0


def probe(path: Path, ffmpeg: str = "ffmpeg") -> VideoInfo:
    out = subprocess.run(
        [ffprobe_for(ffmpeg), "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,nb_frames,avg_frame_rate,duration:format=duration",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    d = json.loads(out)
    st = d["streams"][0]
    duration = float(d.get("format", {}).get("duration") or 0)
    num, den = (st.get("avg_frame_rate") or "0/1").split("/")
    rate = float(num) / float(den) if float(den) else 0
    frames = st.get("nb_frames")
    if frames in (None, "N/A"):
        frames = round(float(st.get("duration") or duration) * rate)
    return VideoInfo(int(st["width"]), int(st["height"]), duration, int(frames), rate)
