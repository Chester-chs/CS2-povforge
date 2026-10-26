"""Put overlays on each recorded clip, add the intro, and join everything."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .media import probe, bounded_size, bounded_fps
from .model import Plan
from .overlay.hud import enable_expr

ANCHORS = {
    "top-left": ("{m}", "{m}"),
    "top-right": ("W-w-{m}", "{m}"),
    "top-center": ("(W-w)/2", "{m}"),
    "bottom-left": ("{m}", "H-h-{m}"),
    "bottom-right": ("W-w-{m}", "H-h-{m}"),
    "bottom-center": ("(W-w)/2", "H-h-{m}"),
    "left-center": ("{m}", "(H-h)/2"),
    "right-center": ("W-w-{m}", "(H-h)/2"),
    "center": ("(W-w)/2", "(H-h)/2"),
}

AUDIO_RATE = 48000


@dataclass
class ComposeSettings:
    minimap_anchor: str = "top-left"
    minimap_margin: int = 24        # pixels at 1080p
    keyboard_anchor: str = "bottom-center"
    keyboard_margin: int = 135      # just above the kill icons of the bottom HUD
    crf: int = 18
    preset: str = "veryfast"
    ffmpeg: str = "ffmpeg"
    chapter_lang: str = "zh"        # chapter titles: "zh" (第18回合 · ACE) or "en" (Round 18 · ACE)


def _xy(anchor: str, margin: float) -> tuple[str, str]:
    if anchor not in ANCHORS:
        raise ValueError(f"Unknown position '{anchor}'. Use one of: {', '.join(ANCHORS)}")
    x, y = ANCHORS[anchor]
    m = str(int(round(margin)))
    return x.format(m=m), y.format(m=m)


def encode_args(s: ComposeSettings) -> list[str]:
    """Identical output settings for every part, so they can be joined without re-encoding."""
    return ["-c:v", "libx264", "-crf", str(s.crf), "-preset", s.preset, "-pix_fmt", "yuv420p",
            "-video_track_timescale", "90000",
            "-c:a", "aac", "-b:a", "192k", "-ar", str(AUDIO_RATE), "-ac", "2"]


def overlay_command(clip: Path, layers: dict[str, Path], out: Path, s: ComposeSettings,
                    scale_to: tuple[int, int] | None = None, height: int = 1080,
                    static_images: dict[str, Path] | None = None, fps: float = 60) -> list[str]:
    """ffmpeg command putting all overlay layers on one clip.

    Stacking order: scope, crosshair, HUD, minimap, keyboard.
    """
    k = height / 1080
    cmd = [s.ffmpeg, "-y", "-loglevel", "error", "-i", str(clip)]
    inputs: list[tuple[str, str, float, str | None]] = []  # (file, anchor, margin, enable)

    static = {}
    if "static" in layers and Path(layers["static"]).exists():
        static = json.loads(Path(layers["static"]).read_text())
    for name in ("scope", "crosshair"):
        img = (static_images or {}).get(name)
        if img is not None and static.get(name):
            inputs.append((str(img), "center", 0, enable_expr(static[name])))
    if "hud" in layers:
        inputs.append((str(layers["hud"]), "bottom-center", 0, None))
    if "minimap" in layers:
        inputs.append((str(layers["minimap"]), s.minimap_anchor, s.minimap_margin * k, None))
    if "keyboard" in layers:
        inputs.append((str(layers["keyboard"]), s.keyboard_anchor, s.keyboard_margin * k, None))

    for f, *_ in inputs:
        cmd += ["-i", f]
    parts, prev = [], "[0:v]"
    if scale_to:
        scale_to = bounded_size(*scale_to)
        parts.append(f"[0:v]scale={scale_to[0]}:{scale_to[1]}:flags=lanczos,setsar=1[v0]")
        prev = "[v0]"
    for i, (_, anchor, margin, enable) in enumerate(inputs, start=1):
        x, y = _xy(anchor, margin)
        opts = f"x={x}:y={y}:eof_action=pass"
        if enable:
            opts += f":enable='{enable}'"
        parts.append(f"{prev}[{i}:v]overlay={opts}[v{i}]")
        prev = f"[v{i}]"
    parts.append(f"{prev}fps={bounded_fps(fps)}[rate]")
    prev = "[rate]"
    if parts:
        cmd += ["-filter_complex", ";".join(parts), "-map", prev]
    else:
        cmd += ["-map", "0:v"]
    cmd += ["-map", "0:a?"] + encode_args(s) + [str(out)]
    return cmd


def safe_filename(name: str) -> str:
    """Player names can contain characters Windows doesn't allow in file names."""
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return cleaned or "player"


def concat_line(p: Path) -> str:
    """One line of an FFmpeg concat list; quotes in the path are escaped."""
    return "file '" + Path(p).resolve().as_posix().replace("'", "'\\''") + "'\n"


def _ts(seconds: float) -> str:
    s = int(seconds)
    h, m, sec = s // 3600, (s // 60) % 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m:02d}:{sec:02d}"


def chapters(plan: Plan, durations: list[float], intro: float = 0.0,
             titles: dict[int, str] | None = None, intro_title: str = "Intro") -> list[tuple[float, float, str]]:
    """(start_s, end_s, title): the intro (if any), then one chapter per round."""
    out, t = [], 0.0
    if intro > 0:
        out.append((0.0, intro, intro_title))
        t = intro
    for seg, dur in zip(plan.segments, durations):
        out.append((t, t + dur, (titles or {}).get(seg.round_number, f"Round {seg.round_number}")))
        t += dur
    return out


def write_chapter_files(plan: Plan, chs: list[tuple[float, float, str]], job_dir: Path) -> tuple[Path, Path]:
    yt = job_dir / "chapters.txt"
    yt.write_text("\n".join(f"{_ts(a)} {title}" for a, _, title in chs) + "\n", encoding="utf-8")
    meta = job_dir / "chapters.ffmetadata"
    lines = [";FFMETADATA1", f"title={plan.player.name} POV - {plan.map_name}"]
    for a, b, title in chs:
        lines += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(a * 1000)}",
                  f"END={int(b * 1000)}", f"title={title}"]
    meta.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return yt, meta


def free_name(folder: Path, stem: str, ext: str = ".mp4") -> Path:
    """folder/stem.ext, or 'stem (2).ext', ... if that is taken."""
    out, n = folder / f"{stem}{ext}", 2
    while out.exists():
        out, n = folder / f"{stem} ({n}){ext}", n + 1
    return out


def compose(plan: Plan, job_dir: Path, clips: list[Path], layers: list[dict[str, Path]],
            fps: float, s: ComposeSettings, size: tuple[int, int] | None = None,
            intro: Path | None = None, static_images: dict[str, Path] | None = None,
            titles: dict[int, str] | None = None) -> Path:
    fps = bounded_fps(fps)
    size = bounded_size(*(size or (1920, 1080)))
    parts_dir = job_dir / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)
    height = size[1] if size else 1080
    parts = []
    for i, (clip, lay) in enumerate(zip(clips, layers)):
        out = parts_dir / f"part_{i:03d}.mp4"
        compatible = False
        if out.exists():
            try:
                cached = probe(out, s.ffmpeg)
                compatible = ((cached.width, cached.height) == size and abs(cached.fps - fps) < 0.01)
            except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
                pass
        if not compatible:
            print(f"Composing {i + 1}/{len(clips)}", flush=True)
            tmp = out.with_name(out.stem + ".tmp.mp4")
            scale_to = None
            if size is not None:
                info = probe(clip, s.ffmpeg)
                if (info.width, info.height) != tuple(size):
                    print(f"  recorded at {info.width}x{info.height}, scaling to {size[0]}x{size[1]}",
                          flush=True)
                    scale_to = size
            subprocess.run(overlay_command(clip, lay, tmp, s, scale_to, height, static_images, fps), check=True)
            tmp.replace(out)
        parts.append(out)

    all_parts = ([intro] if intro else []) + parts
    listing = job_dir / "parts.txt"
    listing.write_text("".join(concat_line(p) for p in all_parts), encoding="utf-8")
    durations = [probe(p, s.ffmpeg).duration for p in parts]
    intro_len = probe(intro, s.ffmpeg).duration if intro else 0.0
    intro_title = "片头" if s.chapter_lang == "zh" else "Intro"
    _, meta = write_chapter_files(plan, chapters(plan, durations, intro_len, titles, intro_title), job_dir)
    final = job_dir / f"{safe_filename(plan.player.name)}_{plan.map_name}_POV.mp4"
    print("Joining parts ...", flush=True)
    subprocess.run([s.ffmpeg, "-y", "-loglevel", "error",
                    "-f", "concat", "-safe", "0", "-i", str(listing),
                    "-i", str(meta), "-map_metadata", "1", "-map_chapters", "1",
                    "-c", "copy", "-movflags", "+faststart", str(final)], check=True)
    from . import video_index
    markers=[]
    for seg in plan.segments[:len(durations)]:
        markers.append([{'at':0,'kind':'round','round':seg.round_number,'player':plan.player.name,
                         'map':plan.map_name,'source':Path(plan.demo_path).name}]+
                       video_index.source_markers(job_dir,plan,seg.round_number))
    video_index.write(final,video_index.flatten(markers,durations,intro_len))
    return final
