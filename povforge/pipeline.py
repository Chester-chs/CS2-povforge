"""End-to-end job: plan -> record -> overlays -> compose.

Every step writes into one job folder and skips work that's already done, so
a job can be stopped and resumed, or run step by step.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd

from .compose import compose, safe_filename
from .config import Config
from . import hlae
import datetime
from dataclasses import asdict

from .demo import TeamStats, PlayerStats, find_player, load_demo, load_hud, load_scoreboard, load_ticks, prepare_demo
from .intro import IntroInfo, make_intro, pretty_map
from .overlay.hud import HudRenderer, crosshair_png, scope_png
from .maps import get_map
from .media import probe
from .model import Plan
from .overlay.keyboard import KeyboardRenderer
from .overlay.minimap import MinimapRenderer
from .overlay.render import render_segment
from .planner import plan_segments
from .timeline import Track, frame_count


def job_dir_for(cfg: Config, demo: Path, player_name: str) -> Path:
    return cfg.output_dir / f"{demo.stem}__{safe_filename(player_name)}"


def _log(msg: str) -> None:
    print(msg, flush=True)


# --- plan ---------------------------------------------------------------------

def parse_rounds(spec: str | None) -> set[int] | None:
    """'1,3,5-7' -> {1, 3, 5, 6, 7}"""
    if not spec:
        return None
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        elif part:
            out.add(int(part))
    return out


def make_plan(cfg: Config, demo_path: str | Path, player_query: str,
              rounds: set[int] | None = None) -> tuple[Plan, Path]:
    source = Path(demo_path)
    demo_path = prepare_demo(demo_path, cfg.output_dir / "demos")
    _log(f"Reading {demo_path.name} ...")
    demo = load_demo(demo_path)
    player = find_player(demo.players, player_query)
    job = job_dir_for(cfg, demo_path, player.name)
    job.mkdir(parents=True, exist_ok=True)

    _log(f"Parsing positions and inputs for {player.name} ...")
    pos, keys = load_ticks(demo_path, player.steamid)
    pos.to_pickle(job / "positions.pkl")
    keys.to_pickle(job / "keys.pkl")
    load_hud(demo_path, player.steamid).to_pickle(job / "hud.pkl")
    track = Track(pos, keys)
    try:
        teams = load_scoreboard(demo_path, len(demo.rounds))
    except Exception as e:  # scoreboard is only for the intro card
        _log(f"Note: no scoreboard for the intro ({e})")
        teams = []
    date = datetime.date.fromtimestamp(source.stat().st_mtime).isoformat()
    (job / "meta.json").write_text(json.dumps({"date": date, "teams": [asdict(t) for t in teams]},
                                              indent=2, ensure_ascii=False), encoding="utf-8")

    segments = plan_segments(
        demo.rounds, demo.deaths, player.steamid, demo.tickrate, demo.last_tick,
        cfg.plan, alive_at=lambda t: track.alive_at(player.steamid, t),
    )
    if rounds:
        segments = [sg for sg in segments if sg.round_number in rounds]
    plan = Plan(str(demo_path.resolve()), demo.map_name, demo.tickrate, player, segments)
    plan_file = job / "plan.json"
    if plan_file.exists() and load_plan(job).segments != plan.segments:
        # The clip list changed: finished clips are numbered by position, so
        # they no longer line up. Raw recordings (per round) are kept.
        for folder in ("clips", "parts"):
            for f in (job / folder).glob("*.mp4"):
                f.unlink()
    plan_file.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")

    mins = plan.total_seconds() / 60
    _log(f"{demo.map_name}: {len(demo.rounds)} rounds, {player.name} played {len(segments)}; "
         f"video length about {mins:.1f} min")
    if not track.has_keys:
        _log("Note: this demo has no input data, the keyboard overlay will stay blank.")
    return plan, job


def load_plan(job: Path) -> Plan:
    return Plan.from_dict(json.loads((job / "plan.json").read_text(encoding="utf-8")))


def load_track(job: Path) -> Track:
    hud = pd.read_pickle(job / "hud.pkl") if (job / "hud.pkl").exists() else None
    return Track(pd.read_pickle(job / "positions.pkl"), pd.read_pickle(job / "keys.pkl"), hud)


def load_meta(job: Path) -> dict:
    f = job / "meta.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


# --- overlays -----------------------------------------------------------------

def _renderers(cfg: Config, plan: Plan):
    scale = cfg.record.height / 1080
    o = cfg.overlay
    minimap = keyboard = hud = None
    if o.minimap:
        try:
            assets = get_map(plan.map_name)
            minimap = MinimapRenderer(assets.info, assets.radar, assets.radar_lower,
                                      size=int(o.minimap_size * scale), show_enemies=o.show_enemies,
                                      place_label=o.place_label)
        except RuntimeError as e:
            _log(f"Minimap disabled: {e}")
    if o.keyboard:
        keyboard = KeyboardRenderer(scale=o.keyboard_scale * scale)
    if o.hud:
        hud = HudRenderer(cfg.record.width, scale)
    return minimap, keyboard, hud


def static_images(cfg: Config, job: Path) -> dict[str, Path]:
    """Crosshair and scope PNGs, drawn once per job."""
    out_dir = job / "overlays"
    out_dir.mkdir(parents=True, exist_ok=True)
    scale = cfg.record.height / 1080
    imgs = {}
    if cfg.overlay.crosshair:
        imgs["crosshair"] = crosshair_png(out_dir / "crosshair.png", scale)
    if cfg.overlay.scope:
        imgs["scope"] = scope_png(out_dir / "scope.png", cfg.record.width, cfg.record.height)
    return imgs


def make_overlays(cfg: Config, job: Path, clips: list[Path] | None = None) -> list[dict[str, Path]]:
    """Render overlays for each clip, matched to the recorded clip's real
    start tick and length when a recording exists."""
    plan, track = load_plan(job), load_track(job)
    minimap, keyboard, hud = _renderers(cfg, plan)
    starts = hlae.actual_starts(job)
    out_dir = job / "overlays"
    results = []
    for i, seg in enumerate(plan.segments):
        cid = hlae.clip_id(seg)
        start = starts.get(cid, float(seg.start_tick))
        frames = None
        if clips is not None and clips[i].exists():
            frames = probe(clips[i], cfg.compose.ffmpeg).frames
        done = out_dir / f"{cid}.done"
        stem = out_dir / cid
        stamp = f"{start}+{frames}@{cfg.record.fps}/{cfg.record.height} {cfg.overlay}"
        if done.exists() and done.read_text() == stamp:
            layers = {k: Path(f"{stem}_{k}.mov") for k in ("minimap", "keyboard", "hud")
                      if Path(f"{stem}_{k}.mov").exists()}
            layers["static"] = Path(f"{stem}_static.json")
        else:
            _log(f"Overlays {i + 1}/{len(plan.segments)} (round {seg.round_number})")
            layers = render_segment(plan, seg, track, out_dir, cfg.record.fps, minimap, keyboard,
                                    cfg.overlay.sync_offset_frames, cfg.compose.ffmpeg,
                                    start_tick=start, frames=frames, hud=hud)
            done.write_text(stamp)
        results.append(layers)
    return results


# --- record -------------------------------------------------------------------

def make_placeholder_clips(cfg: Config, job: Path) -> list[Path]:
    """Grey test clips of the exact recorded length, for checking overlays
    and the whole pipeline on a machine without CS2."""
    plan = load_plan(job)
    clips_dir = job / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    fps, w, h = cfg.record.fps, cfg.record.width, cfg.record.height
    out = []
    for i, seg in enumerate(plan.segments):
        p = clips_dir / f"clip_{i:03d}.mp4"
        if not p.exists():
            _log(f"Test clip {i + 1}/{len(plan.segments)}")
            n = frame_count(seg.start_tick, seg.end_tick, plan.tickrate, fps)
            subprocess.run([
                cfg.compose.ffmpeg, "-y", "-loglevel", "error",
                "-f", "lavfi", "-i", f"color=c=0x3a3f47:s={w}x{h}:r={fps}",
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-frames:v", str(n), "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac", str(p)], check=True)
        out.append(p)
    return out


def make_intro_clip(cfg: Config, job: Path, clips: list[Path]) -> Path | None:
    c = cfg.intro
    if not c.enabled:
        return None
    plan, meta = load_plan(job), load_meta(job)
    teams = [TeamStats(t["name"], t["score"], [PlayerStats(**p) for p in t["players"]])
             for t in meta.get("teams", [])]
    fields = {"player": plan.player.name, "map": pretty_map(plan.map_name),
              "date": c.date or meta.get("date", ""), "width": cfg.record.width,
              "height": cfg.record.height}
    info = IntroInfo(c.title.format(**fields), c.subtitle.format(**fields), plan.player.steamid, teams)
    out = job / "parts" / "intro.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    _log("Making intro ...")
    return make_intro(info, out, (cfg.record.width, cfg.record.height), cfg.record.fps, c.seconds,
                      cfg.compose, clips[0] if clips else None)


def make_video(cfg: Config, job: Path, clips: list[Path]) -> Path:
    layers = make_overlays(cfg, job, clips)
    intro = make_intro_clip(cfg, job, clips)
    return compose(load_plan(job), job, clips, layers, cfg.record.fps, cfg.compose,
                   size=(cfg.record.width, cfg.record.height), intro=intro,
                   static_images=static_images(cfg, job))


def make_recording(cfg: Config, job: Path, placeholder: bool = False) -> list[Path]:
    if placeholder:
        return make_placeholder_clips(cfg, job)
    return hlae.record(load_plan(job), job, cfg.record, cfg.compose.ffmpeg)


# --- all ----------------------------------------------------------------------

def run(cfg: Config, demo: str | Path, player: str, placeholder: bool = False,
        rounds: set[int] | None = None) -> Path:
    _, job = make_plan(cfg, demo, player, rounds)
    clips = make_recording(cfg, job, placeholder)
    final = make_video(cfg, job, clips)
    _log(f"Done: {final.resolve()}")
    return final
