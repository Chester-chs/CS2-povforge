"""Chronological first-person event reels, validated before recording starts."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import shutil

from . import pipeline, effects
from .demo import load_demo, prepare_demo, round_sides, event_round_end
from .hlae import actual_starts, clip_id
from .media import probe


@dataclass(frozen=True)
class View:
    demo: str
    steamid: str
    round: int
    start_tick: int
    end_tick: int
    event_ticks: tuple[int, ...]
    kill_ticks: tuple[int, ...]


def duel_events(demo, sides: dict) -> list[dict]:
    """Only opposing-team kills; halftime CT/T changes are resolved per round."""
    out = []
    for r in demo.rounds:
        side = sides.get(r.number, {})
        for d in sorted(demo.deaths, key=lambda x: x.tick):
            if (r.freeze_end_tick <= d.tick < event_round_end(demo, r)
                    and side.get(d.attacker_steamid) in (2, 3)
                    and side.get(d.victim_steamid) in (2, 3)
                    and side[d.attacker_steamid] != side[d.victim_steamid]):
                out.append({"round": r.number, "tick": d.tick,
                            "attacker": d.attacker_steamid, "victim": d.victim_steamid})
    return out


def load_sources(cfg, items) -> dict:
    sources = {}
    for item in items:
        if item.demo in sources:
            continue
        path = prepare_demo(item.demo, pipeline.work_root(cfg) / "demos")
        data = load_demo(path)
        needs_sides = any(i.demo == item.demo and i.mode == "duel" for i in items)
        sides = round_sides(path, data.rounds) if needs_sides else {}
        sources[item.demo] = data, sides
    return sources


def select_views(items, sources: dict, before: float, after: float) -> list[View]:
    if not items or len({i.mode for i in items}) != 1:
        raise ValueError("Use one content mode per reel.")
    demo_order = {name: i for i, name in enumerate(dict.fromkeys(it.demo for it in items))}
    ordered = sorted(dict.fromkeys(items), key=lambda i: (demo_order[i.demo], i.round))
    views = []
    for item in ordered:
        data, sides = sources[item.demo]
        ids = {p.steamid for p in data.players}
        r = next((r for r in data.rounds if r.number == item.round), None)
        if r is None or item.steamid not in ids:
            raise ValueError("The selected player or round is absent from this demo.")
        round_stop = event_round_end(data, r)
        ds = sorted((d for d in data.deaths if r.freeze_end_tick <= d.tick < round_stop), key=lambda d: d.tick)
        if item.mode == "duel":
            side = sides.get(item.round, {})
            if (item.opponent not in ids or item.opponent == item.steamid
                    or side.get(item.steamid) not in (2, 3) or side.get(item.opponent) not in (2, 3)
                    or side[item.steamid] == side[item.opponent]):
                raise ValueError("Duel players must be on confirmed opposing teams in each selected round.")
            ds = [d for d in ds if {d.attacker_steamid, d.victim_steamid} == {item.steamid, item.opponent}]
        else:
            ds = [d for d in ds if d.victim_steamid == item.steamid or
                  (item.mode == "kills_deaths" and d.attacker_steamid == item.steamid)]
        if not ds:
            raise ValueError(f"Round {item.round} has no events for the selected content mode.")
        solo = []
        for d in ds:
            players = [item.steamid, item.opponent] if item.mode == "duel" else [item.steamid]
            for sid in players:
                a = max(r.freeze_end_tick, int(d.tick - before * data.tickrate))
                b = min(round_stop, max(d.tick + 1, int(d.tick + after * data.tickrate)))
                kills = (d.tick,) if d.attacker_steamid == sid and d.victim_steamid != sid else ()
                view = View(item.demo, sid, item.round, a, b, (d.tick,), kills)
                if item.mode == "duel":
                    views.append(view)
                elif solo and a <= solo[-1].end_tick:
                    prev = solo[-1]
                    solo[-1] = replace(prev, end_tick=max(b, prev.end_tick),
                                       event_ticks=tuple(sorted(set(prev.event_ticks + view.event_ticks))),
                                       kill_ticks=tuple(sorted(set(prev.kill_ticks + kills))))
                else:
                    solo.append(view)
        views.extend(solo)
    return views


def cut_view(view: View, plan, clip: Path, actual: float, duration: float) -> tuple:
    seg = next((s for s in plan.segments if s.round_number == view.round), None)
    if seg is None:
        raise ValueError("No recorded segment covers the selected event.")
    a = max(0.0, (max(view.start_tick, seg.start_tick) - actual) / plan.tickrate)
    b = min(duration, (min(view.end_tick, seg.end_tick) - actual) / plan.tickrate)
    times = [(t - actual) / plan.tickrate for t in view.event_ticks]
    if b <= a or any(t < a or t >= b for t in times):
        raise ValueError("The recording does not contain the selected event; record it again.")
    kills = [(t - actual) / plan.tickrate - a for t in view.kill_ticks]
    return clip, a, b, [k for k in kills if 0 <= k <= b - a]


def run_events(cfg, title, items, placeholder=False, fx=None):
    from . import reel
    fx = effects.normalize(fx)
    pace = effects.pace_seconds(fx, cfg.highlights.before, cfg.highlights.after)
    sources = load_sources(cfg, items)
    views = select_views(items, sources, *pace)  # Validate every source before launching CS2.
    grouped = {}
    for view in views:
        grouped.setdefault((view.demo, view.steamid), []).append(view)
    spans, contexts = {}, {}
    for n, ((demo, sid), wanted) in enumerate(grouped.items(), 1):
        reel._log(f"Reel source {n}/{len(grouped)}: {Path(demo).name}")
        rounds = {v.round for v in wanted}

        def collect(job, plan, clips):
            starts = actual_starts(job)
            for i, seg in enumerate(plan.segments):
                if seg.round_number not in rounds or i >= len(clips) or not clips[i].exists():
                    continue
                actual = starts.get(clip_id(seg), float(seg.start_tick))
                duration = probe(clips[i], cfg.compose.ffmpeg).duration
                for v in (v for v in wanted if v.round == seg.round_number):
                    try:
                        span = cut_view(v, plan, clips[i], actual, duration)
                    except ValueError:
                        continue
                    spans[v] = span
                    contexts[(demo, sid, v.round)] = job, plan

        full = pipeline.whole_match_job(cfg, demo, sid)
        if full is not None:
            plan = pipeline.load_plan(full)
            collect(full, plan, [full / 'clips' / f'clip_{i:03d}.mp4' for i in range(len(plan.segments))])
        missing = [v for v in wanted if v not in spans]
        if missing:
            missing_rounds = {v.round for v in missing}
            # Keep each round from one recording so victim-replay tick mapping stays consistent.
            for view in wanted:
                if view.round in missing_rounds:
                    spans.pop(view, None)
            ticks = sorted({t for v in wanted if v.round in missing_rounds for t in v.event_ticks})
            plan, job = pipeline.make_plan(cfg, demo, sid, missing_rounds, job_suffix='events',
                                           trim_to_kills=pace, event_ticks=ticks)
            collect(job, plan, pipeline.make_recording(cfg, job, placeholder))
    if any(v not in spans for v in views):
        raise RuntimeError("Some selected events are missing from the recordings; no incomplete reel was published.")
    windows = {}
    for v in views:
        windows.setdefault((v.demo, v.steamid, v.round), []).append(spans[v])
    work = pipeline.work_root(cfg)
    from .compose import safe_filename
    try:
        if items[0].mode == 'duel':
            order = [spans[v] for v in views]  # Each encounter stays A then B, even when B got the kill.
        else:
            ordered_items = list(dict.fromkeys(reel.ReelItem(v.demo, v.steamid, v.round) for v in views))
            order = reel._camera_order(cfg, title, ordered_items, windows, contexts, fx, placeholder)
        return reel._plain_join(cfg, title, order) if effects.is_plain(fx) else reel._with_effects(cfg, title, order, fx)
    finally:
        for folder in ('camera pieces', 'reel pieces'):
            shutil.rmtree(work / folder / safe_filename(title), ignore_errors=True)
