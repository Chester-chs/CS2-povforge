"""Local music excerpt selection against the final, effect-adjusted kill timeline."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .media import ffprobe_for

MAX_SECONDS = 3600
RATE = 8000


@dataclass
class Track:
    duration: float
    beats: np.ndarray
    strengths: np.ndarray
    times: np.ndarray
    energy: np.ndarray


def analyze_samples(samples: np.ndarray, rate: int) -> Track:
    """Estimate strong onsets and local energy; no claim to semantic chorus detection."""
    hop = max(1, round(rate * 0.02))
    count = len(samples) // hop
    times = (np.arange(count) + 0.5) * hop / rate
    empty = np.array([], dtype=float)
    if count < 5:
        return Track(len(samples) / rate, empty, empty, times, np.zeros(count))
    rms = np.sqrt(np.mean(np.asarray(samples[:count * hop], dtype=np.float32).reshape(count, hop) ** 2, axis=1))
    peak = float(np.max(rms))
    if peak < 1e-5:
        return Track(len(samples) / rate, empty, empty, times, np.zeros(count))
    # Compare each frame with the preceding 100 ms; sustain is not a fresh beat.
    history = np.convolve(rms, np.ones(5) / 5, mode="full")[:count]
    novelty = np.maximum(0, rms - np.r_[0, history[:-1]])
    threshold = max(float(np.max(novelty)) * 0.12, float(np.median(novelty)) * 3)
    candidates = np.flatnonzero((novelty >= np.r_[0, novelty[:-1]]) &
                               (novelty > np.r_[novelty[1:], 0]) & (novelty > threshold))
    # Non-maximum suppression prevents a single drum hit from becoming several beats.
    selected = []
    occupied = np.zeros(count, dtype=bool)
    gap = max(1, round(0.20 * rate / hop))
    for i in candidates[np.argsort(-novelty[candidates], kind="stable")]:
        if not occupied[i]:
            selected.append(i)
            occupied[max(0, i - gap):min(count, i + gap + 1)] = True
    selected = np.array(sorted(selected), dtype=int)
    width = min(count, max(1, round(rate / hop)))
    energy = np.convolve(rms, np.ones(width) / width, mode="same")
    energy /= max(float(np.max(energy)), 1e-8)
    strengths = novelty[selected] / max(float(np.max(novelty)), 1e-8)
    return Track(len(samples) / rate, times[selected], strengths, times, energy)


def analyze(path: Path, ffmpeg: str = "ffmpeg") -> Track:
    info = subprocess.run([ffprobe_for(ffmpeg), "-v", "error", "-show_entries", "format=duration",
                           "-of", "json", str(path)], capture_output=True, check=True, timeout=30)
    duration = float(json.loads(info.stdout).get("format", {}).get("duration", 0))
    if not 0 < duration <= MAX_SECONDS:
        raise ValueError("Automatic music sync supports tracks up to one hour with a known duration.")
    audio = subprocess.run([ffmpeg, "-v", "error", "-i", str(path), "-t", str(MAX_SECONDS),
                            "-vn", "-ac", "1", "-ar", str(RATE), "-f", "f32le", "pipe:1"],
                           capture_output=True, check=True, timeout=180)
    return analyze_samples(np.frombuffer(audio.stdout, dtype="<f4"), RATE)


def choose_offset(track: Track, kill_times: list[float], total: float) -> dict:
    kills = np.array(sorted(t for t in kill_times if np.isfinite(t) and 0 <= t <= total), dtype=float)
    reason = ("no_kills" if not len(kills) else "music_too_short" if track.duration < total
              else "no_beats" if not len(track.beats) else "")
    if reason:
        return {"start": 0.0, "matched": 0, "errors": [], "reason": reason}
    max_start = track.duration - total
    weights = np.searchsorted(kills, kills + 2, side="right") - np.searchsorted(kills, kills - 2)
    weights = np.maximum(1, weights).astype(float)
    weights /= weights.sum()
    anchors = kills[np.argsort(-weights, kind="stable")[:12]]
    beats = track.beats[np.argsort(-track.strengths, kind="stable")[:512]]
    candidates = (beats[:, None] - anchors).ravel()
    candidates = np.unique(np.r_[0, max_start, np.arange(0, max_start, 1.0),
                                candidates[(candidates >= 0) & (candidates <= max_start)]])
    best_score, best_start = -1.0, 0.0
    for begin in range(0, len(candidates), 128):
        offsets = candidates[begin:begin + 128]
        positions = offsets[:, None] + kills
        right = np.clip(np.searchsorted(track.beats, positions), 0, len(track.beats) - 1)
        left = np.maximum(0, right - 1)
        nearest = np.where(abs(track.beats[left] - positions) <= abs(track.beats[right] - positions), left, right)
        errors = abs(track.beats[nearest] - positions)
        alignment = np.exp(-(errors / 0.08) ** 2) * track.strengths[nearest]
        energy = np.interp(positions, track.times, track.energy)
        scores = ((0.7 * alignment + 0.3 * energy) * weights).sum(axis=1)
        i = int(np.argmax(scores))
        if scores[i] > best_score:
            best_score, best_start = float(scores[i]), float(offsets[i])
    positions = kills + best_start
    right = np.clip(np.searchsorted(track.beats, positions), 0, len(track.beats) - 1)
    left = np.maximum(0, right - 1)
    errors = np.minimum(abs(track.beats[left] - positions), abs(track.beats[right] - positions))
    return {"start": best_start, "matched": int(np.count_nonzero(errors <= 0.08)),
            "errors": errors.tolist(), "reason": ""}


def timeline_kills(moments, chosen, fx, sequence, durations, crossings) -> list[float]:
    """Use all kills, while only the chosen effect scope changes the speed map."""
    from .effects import mapped, time_map
    times, cursor = [], 0.0
    for i, ((kind, value), duration) in enumerate(zip(sequence, durations)):
        if i:
            cursor -= crossings[i - 1]
        if kind == "moment":
            m = moments[value]
            parts = time_map(m.length, chosen[value], fx["slowmo_speed"] if fx["kill_slowmo"] else None)
            times.extend(cursor + mapped(k, parts) for k in m.kills if 0 <= k <= m.length)
        cursor += duration
    return sorted(times)
