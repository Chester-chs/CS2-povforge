"""Put overlays on each recorded clip and join everything into one video."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .model import Plan
from .timeline import frame_count

ANCHORS = {
    "top-left": ("{m}", "{m}"),
    "top-right": ("W-w-{m}", "{m}"),
    "bottom-left": ("{m}", "H-h-{m}"),
    "bottom-right": ("W-w-{m}", "H-h-{m}"),
    "bottom-center": ("(W-w)/2", "H-h-{m}"),
    "top-center": ("(W-w)/2", "{m}"),
}


@dataclass
class ComposeSettings:
    minimap_anchor: str = "top-left"
    keyboard_anchor: str = "bottom-center"
    margin: int = 24
    crf: int = 18
    preset: str = "medium"
    ffmpeg: str = "ffmpeg"


def _xy(anchor: str, margin: int) -> tuple[str, str]:
    if anchor not in ANCHORS:
        raise ValueError(f"Unknown position '{anchor}'. Use one of: {', '.join(ANCHORS)}")
    x, y = ANCHORS[anchor]
    return x.format(m=margin), y.format(m=margin)


def overlay_command(clip: Path, layers: dict[str, Path], out: Path, s: ComposeSettings) -> list[str]:
    cmd = [s.ffmpeg, "-y", "-loglevel", "error", "-i", str(clip)]
    order = [k for k in ("minimap", "keyboard") if k in layers]
    for k in order:
        cmd += ["-i", str(layers[k])]
    if order:
        parts, prev = [], "[0:v]"
        for i, k in enumerate(order, start=1):
            x, y = _xy(getattr(s, f"{k}_anchor"), s.margin)
            tag = f"[v{i}]"
            parts.append(f"{prev}[{i}:v]overlay=x={x}:y={y}:eof_action=pass{tag}")
            prev = tag
        cmd += ["-filter_complex", ";".join(parts), "-map", prev]
    else:
        cmd += ["-map", "0:v"]
    cmd += ["-map", "0:a?",
            "-c:v", "libx264", "-crf", str(s.crf), "-preset", s.preset, "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", str(out)]
    return cmd


def safe_filename(name: str) -> str:
    """Player names can contain characters Windows doesn't allow in file names."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return cleaned or "player"


def _ts(seconds: float) -> str:
    s = int(seconds)
    h, m, sec = s // 3600, (s // 60) % 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def chapters(plan: Plan, fps: float) -> list[tuple[float, float, str]]:
    """(start_s, end_s, title) per round, using exact frame counts."""
    out, t = [], 0.0
    for seg in plan.segments:
        dur = frame_count(seg.start_tick, seg.end_tick, plan.tickrate, fps) / fps
        out.append((t, t + dur, f"Round {seg.round_number}"))
        t += dur
    return out


def write_chapter_files(plan: Plan, fps: float, job_dir: Path) -> tuple[Path, Path]:
    chs = chapters(plan, fps)
    yt = job_dir / "chapters.txt"
    yt.write_text("\n".join(f"{_ts(a)} {title}" for a, _, title in chs) + "\n", encoding="utf-8")
    meta = job_dir / "chapters.ffmetadata"
    lines = [";FFMETADATA1", f"title={plan.player.name} POV - {plan.map_name}"]
    for a, b, title in chs:
        lines += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(a * 1000)}",
                  f"END={int(b * 1000)}", f"title={title}"]
    meta.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return yt, meta


def compose(plan: Plan, job_dir: Path, clips: list[Path], layers: list[dict[str, Path]],
            fps: float, s: ComposeSettings) -> Path:
    parts_dir = job_dir / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    parts = []
    for i, (clip, lay) in enumerate(zip(clips, layers)):
        out = parts_dir / f"part_{i:03d}.mp4"
        if not out.exists():
            print(f"Composing {i + 1}/{len(clips)}", flush=True)
            tmp = out.with_name(out.stem + ".tmp.mp4")
            subprocess.run(overlay_command(clip, lay, tmp, s), check=True)
            tmp.replace(out)
        parts.append(out)

    listing = job_dir / "parts.txt"
    listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), encoding="utf-8")
    _, meta = write_chapter_files(plan, fps, job_dir)
    final = job_dir / f"{safe_filename(plan.player.name)}_{plan.map_name}_POV.mp4"
    print("Joining parts ...", flush=True)
    subprocess.run([s.ffmpeg, "-y", "-loglevel", "error",
                    "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-i", str(meta), "-map_metadata", "1", "-map_chapters", "1",
                    "-c", "copy", "-movflags", "+faststart", str(final)], check=True)
    return final
