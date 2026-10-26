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
import os
import tempfile
import re
from contextlib import contextmanager

from . import effects, camera, hlae
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
    mode: str = "kills"
    opponent: str = ""
    weapons: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.weapons,(list,tuple)) or len(self.weapons)>100:
            raise ValueError('Invalid weapon filter.')
        values=[]
        for weapon in self.weapons:
            if not isinstance(weapon,str): raise ValueError('Invalid weapon filter.')
            weapon=weapon.lower().removeprefix('weapon_')
            if not re.fullmatch(r'[a-z0-9_]{1,48}',weapon): raise ValueError('Invalid weapon filter.')
            values.append(weapon)
        object.__setattr__(self,'weapons',tuple(sorted(set(values))))
        if self.mode not in {"kills", "kill_events", "kills_deaths", "duel"}:
            raise ValueError("Unknown reel content mode.")
        if self.round < 1 or not self.steamid or not self.demo:
            raise ValueError("Choose a demo, player and valid round.")
        if self.mode == "duel" and (not self.opponent or self.opponent == self.steamid):
            raise ValueError("Choose two different opposing players for a duel.")


def load_spec(path: Path) -> tuple[str, list[ReelItem]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = [ReelItem(str(i["demo"]), str(i["steamid"]), int(i["round"]),
                      str(i.get("mode", "kills")), str(i.get("opponent", "")), i.get('weapons',())) for i in data.get("items", [])]
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
    cfg.record.limit_output()
    if any(it.mode != "kills" for it in items):
        from .reel_events import run_events
        return run_events(cfg, title, items, placeholder, fx)
    if any(it.weapons for it in items):
        from .reel_events import load_sources, first_person_kills
        from .demo import event_round_end
        sources=load_sources(cfg,items)
        def matches(item):
            if not item.weapons: return True
            data,_=sources[item.demo]
            r=next((r for r in data.rounds if r.number==item.round),None)
            if r is None: return False
            deaths=[d for d in data.deaths if r.freeze_end_tick<=d.tick<event_round_end(data,r)]
            return any(d.attacker_steamid==item.steamid and (d.weapon or '').lower().removeprefix('weapon_') in item.weapons
                       for d in first_person_kills(deaths))
        items=[it for it in items if matches(it)]
        if not items: raise ValueError('No kills match the selected weapon filter.')
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
    contexts: dict[tuple[str, str, int], tuple[Path, Plan]] = {}
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
                    contexts[(demo, steamid, r)] = (full, pipeline.load_plan(full))
                rounds = rounds - set(got)
        if not rounds:
            continue
        plan, job = pipeline.make_plan(cfg, demo, steamid, rounds, job_suffix="reel", trim_to_kills=room)
        clips = pipeline.make_recording(cfg, job, placeholder)
        for r, spans in _cut_points(cfg, job, rounds, plan, clips, pace=pace).items():
            windows[(demo, steamid, r)] = spans
            contexts[(demo, steamid, r)] = (job, plan)

    missing = [it for it in items if (it.demo, it.steamid, it.round) not in windows]
    for it in missing:
        _log(f"Note: round {it.round} of {Path(it.demo).name} was skipped (the player wasn't in it).")
    if not windows:
        raise RuntimeError("None of the chosen rounds could be used.")
    camera_work = pipeline.work_root(cfg) / "camera pieces" / safe_filename(title)
    try:
        order = _camera_order(cfg, title, items, windows, contexts, fx, placeholder)
        if not effects.is_plain(fx):
            return _with_effects(cfg, title, order, fx)
        return _plain_join(cfg, title, order)
    finally:
        # Failed renders must also release temporary pieces; reusable takes stay.
        reel_work = pipeline.work_root(cfg) / "reel pieces" / safe_filename(title)
        for temporary in (camera_work, reel_work):
            if temporary.is_dir():
                shutil.rmtree(temporary)


def _camera_order(cfg: Config, title: str, items: list[ReelItem], windows: dict,
                  contexts: dict, fx: dict, placeholder: bool = False, *, ordered_spans=None) -> list:
    """Plan around actual kills, batch extra views per demo, then preserve POV audio."""
    sources = (ordered_spans if ordered_spans is not None else
               [((it.demo, it.steamid, it.round), w) for it in items
                for w in windows.get((it.demo, it.steamid, it.round), [])])
    order = [span for _, span in sources]
    choice = camera.normalize_camera(fx.get("camera"))
    if not choice["victim"]:
        return order
    if placeholder:
        _log("Camera shots skipped in placeholder mode (no CS2).")
        return order

    requests, groups = [], {}
    context_cache = {}
    selected = set(choice["selected"]) if choice["selected"] is not None else None
    for source, span in sources:
        demo, steamid, round_number = source
        job, plan = contexts[source]
        if job not in context_cache:
            context_cache[job] = (actual_starts(job), pipeline.load_victims(job) if choice["victim"] else [])
        starts, victims = context_cache[job]
        seg = next(sg for sg in plan.segments if sg.round_number == round_number)
        actual = starts.get(clip_id(seg), float(seg.start_tick))
        demo_key = str(Path(plan.demo_path).resolve()).casefold()
        clip, a, b, kills = span
        start_tick = actual + a * plan.tickrate
        shots = camera.plan_shots(
            start_tick=start_tick, end_tick=actual + b * plan.tickrate,
            kill_ticks=[round(start_tick + k * plan.tickrate) for k in kills],
            victims=victims, steamid=steamid, tickrate=plan.tickrate,
            camera=choice, key=f"{demo_key}:{steamid}:{round_number}", index=len(requests))
        if selected is not None:
            shots = [s for s in shots if camera.event_key(demo, steamid, s["focus"], s["steamid"]) in selected]
        requests.append((span, shots, demo_key, plan.tickrate, actual))
        if shots:
            group = groups.setdefault(demo_key, {"job": job, "plan": plan, "shots": {}})
            for shot in shots:
                group["shots"][shot["id"]] = shot

    for n, group in enumerate(groups.values(), 1):
        shots = list(group["shots"].values())
        _log(f"Camera recording {n}/{len(groups)}: {len(shots)} extra shots "
             "(one CS2 session for this demo; existing shots are reused).")
        paths = hlae.record(group["plan"], group["job"], cfg.record, cfg.compose.ffmpeg,
                            extra_shots=shots, shots_only=True)
        group["paths"] = {shot["id"]: path for shot, path in zip(shots, paths)}
        group["starts"] = actual_starts(group["job"])

    work = pipeline.work_root(cfg) / "camera pieces" / safe_filename(title)
    result, replays = [], []
    for i, (span, shots, demo_key, tickrate, actual) in enumerate(requests):
        if not shots:
            result.append(span)
            continue
        group = groups[demo_key]
        clip, a, b, kills = span
        _log(f"Camera editing {i + 1}/{len(requests)}")
        insertions = []
        for j, shot in enumerate(s for s in shots if s["kind"] == "victim"):
            replay = camera.render_replay(
                clip=clip, start=a, end=b, shot=shot,
                shot_paths=group["paths"], actual_starts=group["starts"], tickrate=tickrate,
                out=work / f"replay_{i:03d}_{j:03d}.mp4", size=(cfg.record.width, cfg.record.height),
                fps=cfg.record.fps, compose=cfg.compose,
            )
            if replay is not None:
                if choice["placement"] == "end":
                    replays.append(replay)
                else:
                    insertions.append(((shot["focus"] - actual) / tickrate + 1 / cfg.record.fps, replay))
        result.extend(camera.interleave_replays(span, insertions, cfg.record.fps))
    return result + replays


@contextmanager
def _reel_destination(final: Path):
    # Stage beside the destination: atomic publication also works across drives.
    fd, name = tempfile.mkstemp(dir=final.parent, prefix=".reel-", suffix=".tmp.mp4")
    os.close(fd)
    staged = Path(name)
    try:
        yield staged
        staged.replace(final)
    finally:
        staged.unlink(missing_ok=True)


def _plain_join(cfg: Config, title: str, order: list) -> Path:
    """Keep the original quick join path when there are no visual/audio effects."""
    cfg.record.limit_output()
    out_dir = pipeline.work_root(cfg) / "reel pieces" / safe_filename(title)
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("piece_*.mp4"):
        f.unlink()
    pieces = []
    for n, (clip, a, b, _) in enumerate(order, 1):
        _log(f"Cutting the reel {n}/{len(order)}")
        piece = out_dir / f"piece_{n:03d}.mp4"
        _cut(clip, a, b, piece, cfg.compose, (cfg.record.width, cfg.record.height), cfg.record.fps)
        pieces.append(piece)
    listing = out_dir / "list.txt"
    listing.write_text("".join(concat_line(p) for p in pieces), encoding="utf-8")
    pipeline.videos_dir(cfg).mkdir(parents=True, exist_ok=True)
    final = free_name(pipeline.videos_dir(cfg), safe_filename(title))
    _log("Joining the reel ...")
    with _reel_destination(final) as staged:
        subprocess.run([cfg.compose.ffmpeg, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", str(listing), "-c", "copy", "-movflags", "+faststart", str(staged)], check=True)
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

    cfg.record.limit_output()

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
    with _reel_destination(final) as staged:
        effects.build(moments, fx, staged, work, (cfg.record.width, cfg.record.height), cfg.record.fps,
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
