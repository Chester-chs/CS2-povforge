"""Render overlay layers for each clip as transparent videos.

Each overlay is written as a QuickTime Animation (qtrle) .mov with an alpha
channel, frame-for-frame aligned with the recorded clip, so compositing is a
plain ffmpeg ``overlay``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..model import Plan, Segment
from ..timeline import Track, frame_count, frame_to_tick
from .keyboard import KeyboardRenderer
from .minimap import MinimapRenderer


class _Sink:
    """Pipe raw RGBA frames into an ffmpeg process."""

    def __init__(self, path: Path, size: tuple[int, int], fps: float, ffmpeg: str = "ffmpeg"):
        self.path = path
        self.proc = subprocess.Popen(
            [ffmpeg, "-y", "-loglevel", "error",
             "-f", "rawvideo", "-pix_fmt", "rgba",
             "-s", f"{size[0]}x{size[1]}", "-r", str(fps), "-i", "-",
             "-c:v", "qtrle", "-pix_fmt", "argb", str(path)],
            stdin=subprocess.PIPE,
        )

    def write(self, data: bytes) -> None:
        self.proc.stdin.write(data)

    def close(self) -> None:
        self.proc.stdin.close()
        if self.proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed writing {self.path}")


def render_segment(
    plan: Plan,
    seg: Segment,
    track: Track,
    out_dir: Path,
    fps: float,
    minimap: MinimapRenderer | None = None,
    keyboard: KeyboardRenderer | None = None,
    offset_frames: float = 0.0,
    ffmpeg: str = "ffmpeg",
    start_tick: float | None = None,
    frames: int | None = None,
) -> dict[str, Path]:
    """Render overlay layers for one clip.

    ``start_tick`` is the demo tick of the clip's first frame (the recorder
    reports the exact value); ``frames`` is the clip's real frame count.
    Both default to the planned values.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    start = seg.start_tick if start_tick is None else start_tick
    n = frames or frame_count(seg.start_tick, seg.end_tick, plan.tickrate, fps)
    me_id = plan.player.steamid
    stem = f"r{seg.round_number:02d}"

    sinks: dict[str, _Sink] = {}
    if minimap is not None:
        sinks["minimap"] = _Sink(out_dir / f"{stem}_minimap.mov", (minimap.size, minimap.size), fps, ffmpeg)
    if keyboard is not None:
        sinks["keyboard"] = _Sink(out_dir / f"{stem}_keyboard.mov", keyboard.size, fps, ffmpeg)

    try:
        for i in range(n):
            tick = frame_to_tick(i, start, plan.tickrate, fps, offset_frames)
            if minimap is not None:
                players = track.players(tick)
                me = next((p for p in players if p.steamid == me_id), None)
                sinks["minimap"].write(minimap.render(me, players))
            if keyboard is not None:
                sinks["keyboard"].write(keyboard.render(track.keys(tick)))
    finally:
        for s in sinks.values():
            s.close()
    return {k: s.path for k, s in sinks.items()}
