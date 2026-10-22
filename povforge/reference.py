"""Preview and describe a selected reference effect before applying a partial patch."""

from __future__ import annotations

import math
import re
import subprocess
import tempfile
from pathlib import Path

from . import style

FIELDS = {
    "flash": ("kill_flash",), "zoom": ("kill_zoom",), "shake": ("kill_shake",),
    "slowmo": ("kill_slowmo", "slowmo_speed"),
    "transition": ("transition", "transition_seconds"),
    "grade": ("grade", "grade_match"),
}


def selected_range(start, end, duration: float) -> tuple[float, float]:
    a, b = float(start), float(end)
    if not all(math.isfinite(v) for v in (a, b, duration)) or not 0 <= a < b <= duration + 0.01:
        raise ValueError("Select a valid start/end time within the video.")
    if b - a > 60:
        raise ValueError("Select at most 60 seconds around the wanted effect.")
    if b - a < 0.25:
        raise ValueError("Select at least 0.25 seconds around the wanted effect.")
    return a, min(b, duration)


def byte_range(header: str, size: int) -> tuple[int, int]:
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", header)
    if not match or not any(match.groups()) or size <= 0:
        raise ValueError("Invalid byte range")
    a, b = match.groups()
    start = int(a) if a else max(0, size - int(b))
    end = min(size - 1, int(b)) if a and b else size - 1
    if not 0 <= start <= end < size:
        raise ValueError("Unsatisfiable byte range")
    return start, end


def effect_kind(kind: str, description: str) -> str:
    text = description.lower()
    if kind == "object" or any(x in text for x in ("刀身", "环绕", "光环", "刀光", "跟踪", "粒子", "knife", "tracking", "particle", "aura")):
        return "object"
    if kind in FIELDS:
        return kind
    if kind == "auto":
        for key, words in {"flash": ("闪白", "白闪", "flash"), "slowmo": ("慢动作", "慢放", "slow"),
                           "zoom": ("放大", "缩放", "zoom"), "shake": ("震动", "抖动", "shake"),
                           "transition": ("转场", "transition"), "grade": ("调色", "滤镜", "colour", "color")}.items():
            if any(w in text for w in words):
                return key
    return "unknown"


def propose(analysis: dict, kind: str, description: str) -> dict:
    kind = effect_kind(kind, description)
    if kind not in FIELDS:
        return {"kind": kind, "status": "unsupported", "patch": {},
                "reason": "object_tracking" if kind == "object" else "unknown_effect"}
    fx = analysis.get("effects", {})
    first = FIELDS[kind][0]
    detected = fx.get(first) not in (None, False, "none", "cut")
    return {"kind": kind, "status": "detected" if detected else "not_detected",
            "patch": {key: fx[key] for key in FIELDS[kind] if key in fx} if detected else {},
            "reason": "template_approximation" if detected else "no_evidence"}


def prepare(source: str, folder: Path, ffmpeg: str = "ffmpeg") -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    if style.is_link(source):
        video, title = style.fetch(source, folder, ffmpeg)
    else:
        video, title = Path(source).resolve(), Path(source).stem
        if not video.is_file():
            raise ValueError("The reference video was not found.")
    info = style.video_info(video, ffmpeg)
    if not 0 < info["duration"] <= style.MAX_SECONDS:
        raise ValueError("Import a reference up to 15 minutes long; trim a longer source first.")
    preview = folder / "preview.mp4"
    subprocess.run([ffmpeg, "-y", "-v", "error", "-i", str(video), "-map", "0:v:0", "-map", "0:a?",
                    "-vf", "scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2,fps=30,setsar=1",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(preview)],
                   capture_output=True, check=True, timeout=600)
    return {"source": str(video), "preview": str(preview), "title": title, "duration": info["duration"]}


def analyze_selection(source: str, start, end, kind: str, description: str, ffmpeg: str = "ffmpeg") -> dict:
    info = style.video_info(Path(source), ffmpeg)
    a, b = selected_range(start, end, info["duration"])
    request = {"start": a, "end": b, "description": description[:500]}
    if effect_kind(kind, description) not in FIELDS:
        return {"proposal": propose({}, kind, description), "request": request, "report": []}
    with tempfile.TemporaryDirectory(prefix="povforge-selection-") as tmp:
        clip = Path(tmp) / "selection.mp4"
        subprocess.run([ffmpeg, "-y", "-v", "error", "-ss", str(a), "-i", source, "-t", str(b - a),
                        "-map", "0:v:0", "-map", "0:a?", "-vf",
                        "scale=1920:1080:force_original_aspect_ratio=decrease:force_divisible_by=2",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-c:a", "aac", str(clip)],
                       capture_output=True, check=True, timeout=180)
        analysis = style.analyze(clip, ffmpeg, min_occurrences=1)
    return {"proposal": propose(analysis, kind, description), "request": request,
            "report": analysis.get("report", [])}
