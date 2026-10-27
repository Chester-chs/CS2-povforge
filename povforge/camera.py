"""Plan, render and place optional first-person victim replays."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

from .compose import ComposeSettings, encode_args
from .media import ffprobe_for, probe


_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _number(value, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value) if math.isfinite(value) else default


# A victim replay shows the last seconds before death and the body going down
# after it, from the victim's own view (owner request; fixed, not a setting).
VICTIM_BEFORE = 3.0   # seconds before the death
VICTIM_AFTER = 1.0    # seconds after the death


def normalize_camera(raw) -> dict:
    """Migrate legacy camera preferences to first-person-only recording.

    Victim replays are one switch: on replays every kill in the reel. A legacy
    per-kill ``selected`` list is dropped (an empty one used to mean "none")."""
    raw = raw if isinstance(raw, dict) else {}
    return {"mode": "pov", "victim": raw.get("victim") is True,
            "placement": "end" if raw.get("placement") == "end" else "after_kill",
            "durations": {"before": VICTIM_BEFORE, "after": VICTIM_AFTER}}


def interleave_replays(span: tuple, insertions: list, fps: float) -> list:
    """Split the main clip on output-frame boundaries; retain each frame once."""
    if not insertions:
        return [span]
    clip, start, end, kills = span
    result, cursor = [], start

    def main(a, b):
        return clip, a, b, [start + k - a for k in kills if a <= start + k < b]

    for at, replay in sorted(insertions, key=lambda entry: entry[0]):
        boundary = min(end, max(cursor, start + math.ceil((at - start) * fps - 1e-8) / fps))
        if boundary > cursor + 1e-8:
            result.append(main(cursor, boundary))
        result.append(replay)
        cursor = boundary
    if cursor < end - 1e-8:
        result.append(main(cursor, end))
    return result


def _victim_map(victims) -> dict[float, list[str]]:
    rows = victims.items() if isinstance(victims, dict) else victims or []
    out = {}
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            continue
        tick, sid = row
        # JSON object keys may be strings, unlike the preferred pair list.
        try:
            t = float(tick)
        except (TypeError, ValueError):
            continue
        if math.isfinite(t) and isinstance(sid, (str, int)) and not isinstance(sid, bool):
            sid = str(sid).strip()
            if sid.isascii() and sid.isdecimal() and 1 <= len(sid) <= 20 and int(sid) > 0:
                group = out.setdefault(t, [])
                if sid not in group:
                    group.append(sid)
    return out


def plan_shots(*, start_tick: float, end_tick: float, kill_ticks, victims,
               steamid: str, tickrate: float, camera, key: str, index: int = 0) -> list[dict]:
    """Plan one first-person replay per known victim, in kill order.

    Placement is decided during assembly. Legacy third-person flags are ignored.
    """
    cfg = normalize_camera(camera)
    rate = _number(tickrate, 0)
    begin, finish = _number(start_tick, 0), _number(end_tick, 0)
    if not cfg["victim"] or rate <= 0 or finish <= begin:
        return []
    kills = sorted({int(t) for t in kill_ticks
                    if not isinstance(t, bool) and isinstance(t, (int, float))
                    and math.isfinite(t) and int(t) == t and begin <= t < finish})
    length = (finish - begin) / rate
    known, shots = _victim_map(victims), []
    for focus in kills:
        # Before the death in first person, then whatever CS2 shows of the victim
        # dying for a moment after it; the moment's own range bounds both (the
        # replay plays the main footage's sound for the same demo time).
        start = max(math.ceil(begin), focus - round(VICTIM_BEFORE * rate))
        end = min(math.floor(finish), focus + round(VICTIM_AFTER * rate))
        if (focus - start) / rate < .35 or end <= focus:
            continue
        for sid in known.get(focus, []):
            if sid == str(steamid):
                continue
            identity = [str(key), str(steamid), sid, "victim", start, end, focus]
            digest = hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()[:20]
            shots.append({"id": f"shot_victim_{digest}", "start": start, "end": end,
                          "steamid": sid, "cam": "pov", "focus": focus, "death": focus, "kind": "victim",
                          "at": length, "until": length, "insert": True,
                          "audio_at": (start - begin) / rate})
    return shots


def _has_audio(path: Path, ffmpeg: str) -> bool:
    result = subprocess.run(
        [ffprobe_for(ffmpeg), "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True, creationflags=_NO_WINDOW)
    return bool(result.stdout.strip())


def _prepare_shots(*, start: float, end: float, shots: list[dict], shot_paths: dict,
                   actual_starts: dict, tickrate: float, fps: float,
                   compose: ComposeSettings) -> list[dict]:
    """Align real recorded frames and sound to the source demo timeline."""
    if tickrate <= 0 or fps <= 0 or end <= start:
        raise ValueError("Camera rendering needs a valid time range, tick rate and frame rate.")
    length = end - start
    frame = 1 / fps
    usable = []

    def fallback(shot, reason):
        print(f"Victim replay {shot['id']}: {reason}; skipping replay.", flush=True)

    for shot in shots:
        if shot.get("kind") != "victim" or shot.get("cam") != "pov":
            raise ValueError("Only first-person victim replays can be appended.")
        sid = shot["id"]
        path = shot_paths.get(sid)
        if path is None or not Path(path).is_file():
            fallback(shot, "recording is missing")
            continue
        duration = (shot["end"] - shot["start"]) / tickrate
        duration = math.floor((duration + 1e-9) * fps) / fps
        audio_at = _number(shot.get("audio_at"), float("nan"))
        if not math.isfinite(audio_at) or audio_at < 0 or audio_at + duration > length + frame / 2:
            fallback(shot, "its replay audio time is unknown or outside this moment")
            continue
        actual = _number(actual_starts.get(sid), float("nan"))
        if not math.isfinite(actual):
            fallback(shot, "its actual recording start is unknown")
            continue
        offset = (shot["start"] - actual) / tickrate
        try:
            info = probe(Path(path), compose.ffmpeg)
        except (OSError, ValueError, KeyError, subprocess.CalledProcessError):
            fallback(shot, "the recording could not be read")
            continue
        source_fps = info.fps or fps
        first_frame = round(offset * source_fps)
        wanted_frames = round(duration * source_fps)
        missing_head = max(0, -first_frame)
        missing_tail = max(0, first_frame + wanted_frames - info.frames)
        kept_frames = wanted_frames - missing_head - missing_tail
        # HLAE starts/stops on rendered frames while demo events use ticks. Keep
        # real frames at a small quantized boundary, never invent missing video
        # from a longer audio/container duration. Larger gaps still reject it.
        edge = max(2 * frame, 1 / tickrate) + 1e-8
        # After the death CS2 may move the camera off the victim; the director
        # then stops early, so a shorter after-death tail is expected and kept.
        death = _number(shot.get("death"), float("nan"))
        after = max(0.0, (shot["end"] - death) / tickrate) if math.isfinite(death) else 0.0
        if (duration < frame or kept_frames <= 0
                or missing_head / source_fps > edge or missing_tail / source_fps > edge + after):
            fallback(shot, "the recording does not cover the requested time")
            continue
        first_frame = max(0, first_frame)
        duration = math.floor((kept_frames / source_fps + 1e-9) * fps) / fps
        if duration < frame:
            fallback(shot, "the recording has no complete output frame")
            continue
        offset = first_frame / source_fps
        audio_at += (actual - shot["start"]) / tickrate + offset
        if audio_at < 0 or audio_at + duration > length + frame / 2:
            fallback(shot, "the trimmed replay audio is outside this moment")
            continue
        if missing_head or missing_tail:
            print(f"Camera {shot.get('kind', 'shot')}: using {kept_frames} recorded frames; "
                  "unrecorded replay edges are omitted.", flush=True)
        usable.append({**shot, "path": Path(path), "offset": offset, "source_fps": source_fps,
                       "audio_at": audio_at, "duration": duration})
    return usable


def render_replay(*, clip: Path, start: float, end: float, shot: dict,
                  shot_paths: dict, actual_starts: dict, tickrate: float,
                  out: Path, size: tuple[int, int], fps: float,
                  compose: ComposeSettings) -> tuple[Path, float, float, list[float]] | None:
    """Render one independent victim replay with matching source-time sound.

    Missing footage is skipped. Small capture gaps trim the replay to real
    frames and align the original demo audio with the retained picture.
    """
    usable = _prepare_shots(start=start, end=end, shots=[shot], shot_paths=shot_paths,
                           actual_starts=actual_starts, tickrate=tickrate, fps=fps, compose=compose)
    if not usable:
        return None
    view = usable[0]
    first = round(view["offset"] * view["source_fps"])
    frames = round(view["duration"] * view["source_fps"])
    duration = view["duration"]
    audio_at = start + view["audio_at"]
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [compose.ffmpeg, "-y", "-v", "error", "-filter_complex_threads", "1",
           "-i", str(clip), "-i", str(view["path"])]
    audio_input = 0
    if not _has_audio(Path(clip), compose.ffmpeg):
        audio_input = 2
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    width, height = size
    filters = [
        f"[1:v]trim=start_frame={first}:end_frame={first + frames},setpts=PTS-STARTPTS,"
        f"scale={width}:{height}:flags=lanczos,setsar=1,fps={fps},format=yuv420p[vout]",
        f"[{audio_input}:a]atrim=start={audio_at:.9f}:duration={duration:.9f},asetpts=PTS-STARTPTS,"
        f"aresample=48000,aformat=channel_layouts=stereo,apad=whole_dur={duration:.9f},"
        f"atrim=duration={duration:.9f}[aout]",
    ]
    cmd += ["-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]"]
    cmd += encode_args(compose) + ["-t", f"{duration:.9f}", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, creationflags=_NO_WINDOW)
    return out, 0.0, probe(out, compose.ffmpeg).duration, []
