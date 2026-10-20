"""Highlight reel: the kills of chosen rounds, from one or several demos and
players, joined in the order the user picked.

Each chosen round becomes one continuous piece, from a few seconds before
its first kill to just after its last. Only the game picture is used (the game's own HUD stays; no minimap, keys,
intro or captions). Each demo/player pair is planned and recorded on its own
(one CS2 session per demo), only around the kills of the chosen rounds; the
kill moments are then cut out and joined, with the effects chosen for the reel
(see effects.py), or plainly when none were chosen.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import shutil

from . import effects
from .compose import concat_line, free_name, safe_filename
from .config import Config
from .extras import _cut, kill_windows
from .hlae import actual_starts, clip_id
from .media import probe
from . import pipeline
from .model import Plan


@dataclass(frozen=True)
class ReelItem:
    demo: str
    steamid: str
    round: int


def load_spec(path: Path) -> tuple[str, list[ReelItem]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = [ReelItem(str(i["demo"]), str(i["steamid"]), int(i["round"])) for i in data.get("items", [])]
    if not items:
        raise ValueError("The highlight reel has no rounds.")
    return str(data.get("title") or "Highlights"), items


def load_effects(path: Path) -> dict:
    """The effects chosen for the reel (``effects`` in the spec), all settings filled in."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return effects.normalize(data.get("effects"))


def _log(msg: str) -> None:
    print(msg, flush=True)


def _cut_points(cfg: Config, job: Path, rounds: set[int], plan=None, clips=None,
                pace: tuple[float, float] | None = None) -> dict[int, list]:
    """For each wanted round recorded in ``job``: the part to use, one continuous
    piece from just before its first kill to just after its last (nothing cut
    out in between), as (clip, start, end, kill times from the start). Rounds
    without a recorded clip are left out."""
    h = cfg.highlights
    before, after = pace or (h.before, h.after)
    plan = plan or pipeline.load_plan(job)
    if clips is None:
        clips = [job / "clips" / f"clip_{i:03d}.mp4" for i in range(len(plan.segments))]
    keep = [i for i, seg in enumerate(plan.segments) if seg.round_number in rounds and clips[i].exists()]
    if not keep:
        return {}
    sub = Plan(plan.demo_path, plan.map_name, plan.tickrate, plan.player, [plan.segments[i] for i in keep])
    sub_clips = [clips[i] for i in keep]
    kf = job / "kills.json"
    kills = [(int(t), bool(hs)) for t, hs in json.loads(kf.read_text())] if kf.exists() else []
    durations = [probe(c, cfg.compose.ffmpeg).duration for c in sub_clips]
    starts = actual_starts(job)
    found = kill_windows(sub, starts, kills, durations, before, after, float("inf"))
    out: dict[int, list] = {}
    for i, a, b in found:
        seg = sub.segments[i]
        t0 = starts.get(clip_id(seg), float(seg.start_tick))
        times = sorted((t - t0) / plan.tickrate - a for t, _ in kills if seg.start_tick <= t <= seg.end_tick)
        out.setdefault(seg.round_number, []).append((sub_clips[i], a, b, [x for x in times if 0 <= x <= b - a]))
    for seg, clip, dur in zip(sub.segments, sub_clips, durations):
        # a chosen round without kills (a clutch won on the bomb): its last seconds
        out.setdefault(seg.round_number, [(clip, max(0.0, dur - 8.0), dur, [])])
    return out


def run(cfg: Config, title: str, items: list[ReelItem], placeholder: bool = False,
        fx: dict | None = None) -> Path:
    h = cfg.highlights
    fx = effects.normalize(fx)
    pace = effects.pace_seconds(fx, h.before, h.after)
    # record with at least the usual room around the kills, so earlier recordings still fit
    room = (max(pace[0], h.before), max(pace[1], h.after))
    # one source per demo + player, in the order they first appear
    sources: dict[tuple[str, str], set[int]] = {}
    for it in items:
        sources.setdefault((it.demo, it.steamid), set()).add(it.round)

    windows: dict[tuple[str, str, int], list[tuple[Path, float, float, list[float]]]] = {}
    for n, ((demo, steamid), rounds) in enumerate(sources.items(), 1):
        _log(f"Reel source {n}/{len(sources)}: {Path(demo).name}")
        # rounds already recorded for the whole-match video are cut from there:
        # no reading the demo again, no CS2
        full = pipeline.whole_match_job(cfg, demo, steamid)
        if full is not None:
            got = _cut_points(cfg, full, rounds, pace=pace)
            if got:
                _log(f"Using the whole-match recording for round(s) {', '.join(map(str, sorted(got)))}")
                for r, spans in got.items():
                    windows[(demo, steamid, r)] = spans
                rounds = rounds - set(got)
        if not rounds:
            continue
        plan, job = pipeline.make_plan(cfg, demo, steamid, rounds, job_suffix="reel", trim_to_kills=room)
        clips = pipeline.make_recording(cfg, job, placeholder)
        for r, spans in _cut_points(cfg, job, rounds, plan, clips, pace=pace).items():
            windows[(demo, steamid, r)] = spans

    missing = [it for it in items if (it.demo, it.steamid, it.round) not in windows]
    for it in missing:
        _log(f"Note: round {it.round} of {Path(it.demo).name} was skipped (the player wasn't in it).")
    order = [w for it in items for w in windows.get((it.demo, it.steamid, it.round), [])]
    if not order:
        raise RuntimeError("None of the chosen rounds could be used.")
    if not effects.is_plain(fx):
        return _with_effects(cfg, title, order, fx)

    out_dir = pipeline.work_root(cfg) / "reel pieces" / safe_filename(title)
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("piece_*.mp4"):
        f.unlink()
    pieces = []
    for n, (clip, a, b, _) in enumerate(order, 1):
        _log(f"Cutting the reel {n}/{len(order)}")
        piece = out_dir / f"piece_{n:03d}.mp4"
        _cut(clip, a, b, piece, cfg.compose)
        pieces.append(piece)
    listing = out_dir / "list.txt"
    listing.write_text("".join(concat_line(p) for p in pieces), encoding="utf-8")
    pipeline.videos_dir(cfg).mkdir(parents=True, exist_ok=True)
    final = free_name(pipeline.videos_dir(cfg), safe_filename(title))
    _log("Joining the reel ...")
    subprocess.run([cfg.compose.ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(final)], check=True)
    shutil.rmtree(out_dir, ignore_errors=True)       # the pieces are cut again from the recordings if needed
    try:
        out_dir.parent.rmdir()                       # gone too when no other reel is being cut
    except OSError:
        pass
    seconds = sum(w[2] - w[1] for w in order)
    _log(f"Reel: {len(order)} moments, {seconds:.0f} s")
    _log(f"Done: {final.resolve()}")
    return final


def _with_effects(cfg: Config, title: str, order: list, fx: dict) -> Path:
    """Put the reel together with its effects (effects.py)."""
    from .style import colour_stats

    _log("Effects: " + (", ".join(effects.describe(fx)) or "none"))
    moments = [effects.Moment(clip, a, b, kills) for clip, a, b, kills in order]
    stats = None
    if fx["grade"] == "match":
        _log("Effects: measuring the colours ...")
        stats = colour_stats([(m.clip, m.start, m.length) for m in moments], cfg.compose.ffmpeg)
    work = pipeline.work_root(cfg) / "reel pieces" / safe_filename(title)
    shutil.rmtree(work, ignore_errors=True)
    pipeline.videos_dir(cfg).mkdir(parents=True, exist_ok=True)
    final = free_name(pipeline.videos_dir(cfg), safe_filename(title))
    _log("Joining the reel ...")
    effects.build(moments, fx, final, work, (cfg.record.width, cfg.record.height), cfg.record.fps,
                  cfg.compose, title=title, source_stats=stats)
    shutil.rmtree(work, ignore_errors=True)
    try:
        work.parent.rmdir()
    except OSError:
        pass
    seconds = probe(final, cfg.compose.ffmpeg).duration
    _log(f"Reel: {len(moments)} moments, {seconds:.0f} s")
    _log(f"Done: {final.resolve()}")
    return final
