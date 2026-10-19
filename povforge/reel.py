"""Highlight reel: the kills of chosen rounds, from one or several demos and
players, joined in the order the user picked.

Each chosen round becomes one continuous piece, from a few seconds before
its first kill to just after its last. Only the game picture is used (the game's own HUD stays; no minimap, keys,
intro or captions). Each demo/player pair is planned and recorded on its own
(one CS2 session per demo), only around the kills of the chosen rounds; the
kill moments are then cut out and joined.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import shutil

from .compose import free_name, safe_filename
from .config import Config
from .extras import _cut, kill_windows
from .hlae import actual_starts
from .media import probe
from . import pipeline


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


def _log(msg: str) -> None:
    print(msg, flush=True)


def run(cfg: Config, title: str, items: list[ReelItem], placeholder: bool = False) -> Path:
    h = cfg.highlights
    # one source per demo + player, in the order they first appear
    sources: dict[tuple[str, str], set[int]] = {}
    for it in items:
        sources.setdefault((it.demo, it.steamid), set()).add(it.round)

    windows: dict[tuple[str, str, int], list[tuple[Path, float, float]]] = {}
    for n, ((demo, steamid), rounds) in enumerate(sources.items(), 1):
        _log(f"Reel source {n}/{len(sources)}: {Path(demo).name}")
        plan, job = pipeline.make_plan(cfg, demo, steamid, rounds, job_suffix="reel",
                                       trim_to_kills=(h.before, h.after))
        clips = pipeline.make_recording(cfg, job, placeholder)
        kills = [(int(t), bool(hs)) for t, hs in json.loads((job / "kills.json").read_text())]
        durations = [probe(c, cfg.compose.ffmpeg).duration for c in clips]
        # one continuous piece per round: from just before the first kill to just
        # after the last, nothing cut out in between
        found = kill_windows(plan, actual_starts(job), kills, durations, h.before, h.after, float("inf"))
        by_round: dict[int, list] = {}
        for i, a, b in found:
            by_round.setdefault(plan.segments[i].round_number, []).append((clips[i], a, b))
        for i, (seg, clip, dur) in enumerate(zip(plan.segments, clips, durations)):
            # a chosen round without kills (a clutch won on the bomb): its last seconds
            spans = by_round.get(seg.round_number) or [(clip, max(0.0, dur - 8.0), dur)]
            windows[(demo, steamid, seg.round_number)] = spans

    missing = [it for it in items if (it.demo, it.steamid, it.round) not in windows]
    for it in missing:
        _log(f"Note: round {it.round} of {Path(it.demo).name} was skipped (the player wasn't in it).")
    order = [(c, a, b) for it in items for c, a, b in windows.get((it.demo, it.steamid, it.round), [])]
    if not order:
        raise RuntimeError("None of the chosen rounds could be used.")

    out_dir = pipeline.work_root(cfg) / "reel pieces" / safe_filename(title)
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("piece_*.mp4"):
        f.unlink()
    pieces = []
    for n, (clip, a, b) in enumerate(order, 1):
        _log(f"Cutting the reel {n}/{len(order)}")
        piece = out_dir / f"piece_{n:03d}.mp4"
        _cut(clip, a, b, piece, cfg.compose)
        pieces.append(piece)
    listing = out_dir / "list.txt"
    listing.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in pieces), encoding="utf-8")
    final = free_name(cfg.output_dir, safe_filename(title))
    _log("Joining the reel ...")
    subprocess.run([cfg.compose.ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(final)], check=True)
    shutil.rmtree(out_dir, ignore_errors=True)       # the pieces are cut again from the recordings if needed
    try:
        out_dir.parent.rmdir()                       # gone too when no other reel is being cut
    except OSError:
        pass
    seconds = sum(b - a for _, a, b in order)
    _log(f"Reel: {len(order)} moments, {seconds:.0f} s")
    _log(f"Done: {final.resolve()}")
    return final
