"""End-to-end job: plan -> overlays -> record -> compose.

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
from .csvg import record, write_compilation
from .demo import find_player, load_demo, load_ticks, prepare_demo
from .maps import get_map
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
    track = Track(pos, keys)

    segments = plan_segments(
        demo.rounds, demo.deaths, player.steamid, demo.tickrate, demo.last_tick,
        cfg.plan, alive_at=lambda t: track.alive_at(player.steamid, t),
    )
    if rounds:
        segments = [sg for sg in segments if sg.round_number in rounds]
    plan = Plan(str(demo_path.resolve()), demo.map_name, demo.tickrate, player, segments)
    plan_file = job / "plan.json"
    if plan_file.exists() and load_plan(job).segments != plan.segments:
        # The clip list changed: earlier recordings no longer line up.
        for folder in ("clips", "parts"):
            for f in (job / folder).glob("*.mp4"):
                f.unlink()
    plan_file.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
    write_compilation(plan, job, cfg.record)

    mins = plan.total_seconds() / 60
    _log(f"{demo.map_name}: {len(demo.rounds)} rounds, {player.name} played {len(segments)}; "
         f"video length about {mins:.1f} min")
    if not track.has_keys:
        _log("Note: this demo has no input data, the keyboard overlay will stay blank.")
    return plan, job


def load_plan(job: Path) -> Plan:
    return Plan.from_dict(json.loads((job / "plan.json").read_text(encoding="utf-8")))


def load_track(job: Path) -> Track:
    return Track(pd.read_pickle(job / "positions.pkl"), pd.read_pickle(job / "keys.pkl"))


# --- overlays -----------------------------------------------------------------

def _renderers(cfg: Config, plan: Plan):
    scale = cfg.record.height / 1080
    o = cfg.overlay
    minimap = keyboard = None
    if o.minimap:
        try:
            assets = get_map(plan.map_name)
            minimap = MinimapRenderer(assets.info, assets.radar, assets.radar_lower,
                                      size=int(o.minimap_size * scale), show_enemies=o.show_enemies)
        except RuntimeError as e:
            _log(f"Minimap disabled: {e}")
    if o.keyboard:
        keyboard = KeyboardRenderer(scale=o.keyboard_scale * scale)
    return minimap, keyboard


def make_overlays(cfg: Config, job: Path) -> list[dict[str, Path]]:
    plan, track = load_plan(job), load_track(job)
    minimap, keyboard = _renderers(cfg, plan)
    out_dir = job / "overlays"
    results = []
    for i, seg in enumerate(plan.segments, 1):
        done = out_dir / f"r{seg.round_number:02d}.done"
        stem = out_dir / f"r{seg.round_number:02d}"
        stamp = f"{seg.start_tick}-{seg.end_tick}@{cfg.record.fps}/{cfg.record.height} {cfg.overlay}"
        if done.exists() and done.read_text() == stamp:
            layers = {k: Path(f"{stem}_{k}.mov") for k in ("minimap", "keyboard")
                      if Path(f"{stem}_{k}.mov").exists()}
        else:
            _log(f"Overlays {i}/{len(plan.segments)} (round {seg.round_number})")
            layers = render_segment(plan, seg, track, out_dir, cfg.record.fps, minimap, keyboard,
                                    cfg.overlay.sync_offset_frames, cfg.compose.ffmpeg)
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
            n = frame_count(seg.start_tick, seg.end_tick, plan.tickrate, fps)
            label = f"Round {seg.round_number}"
            subprocess.run([
                cfg.compose.ffmpeg, "-y", "-loglevel", "error",
                "-f", "lavfi", "-i", f"color=c=0x3a3f47:s={w}x{h}:r={fps}",
                "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                "-vf", f"drawtext=text='{label}':fontcolor=white:fontsize={h // 12}"
                       ":x=(w-tw)/2:y=(h-th)/2",
                "-frames:v", str(n), "-shortest", "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac", str(p)], check=True)
        out.append(p)
    return out


def make_recording(cfg: Config, job: Path, placeholder: bool = False) -> list[Path]:
    if placeholder:
        return make_placeholder_clips(cfg, job)
    return record(load_plan(job), job, cfg.record)


# --- all ----------------------------------------------------------------------

def run(cfg: Config, demo: str | Path, player: str, placeholder: bool = False,
        rounds: set[int] | None = None) -> Path:
    _, job = make_plan(cfg, demo, player, rounds)
    layers = make_overlays(cfg, job)
    clips = make_recording(cfg, job, placeholder)
    final = compose(load_plan(job), job, clips, layers, cfg.record.fps, cfg.compose)
    _log(f"Done: {final}")
    return final
