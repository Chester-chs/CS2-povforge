"""End-to-end job: plan -> record -> overlays -> compose.

Every step writes into one job folder and skips work that's already done, so
a job can be stopped and resumed, or run step by step.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd

from .compose import compose, free_name, safe_filename
from .config import Config
from . import faceit, highlights, hlae
import datetime
from dataclasses import asdict

import pickle

from .demo import (PlayerStats, TeamStats, find_player, load_demo, load_hud, load_scoreboard,
                   load_ticks, load_utility, prepare_demo)
from .intro import IntroInfo, make_intro, pretty_map
from .overlay.hud import HudRenderer, crosshair_png, scope_png
from .maps import get_map
from .media import probe
from .model import Plan, Segment
from .overlay.keyboard import KeyboardRenderer
from .overlay.minimap import MinimapRenderer
from .overlay.playerbar import PlayerBarRenderer
from .overlay.render import render_segment
from .planner import plan_segments
from .timeline import Track, frame_count


def work_root(cfg: Config) -> Path:
    """Where recordings and other intermediate files live (a subfolder of the output folder)."""
    return cfg.output_dir / cfg.work_dir_name


def videos_dir(cfg: Config) -> Path:
    """Where finished videos go (the output folder, or the player's folder in it)."""
    return cfg.video_dir or cfg.output_dir


def job_dir_for(cfg: Config, demo: Path, player_name: str, suffix: str = "") -> Path:
    return work_root(cfg) / f"{demo.stem}__{safe_filename(player_name)}{'__' + suffix if suffix else ''}"


def publish(cfg: Config, job: Path, made: Path) -> Path:
    """Move a finished video out of the job folder into the output folder. A job
    keeps the same name on later runs; a new job never overwrites another's video."""
    rec = job / "published.json"
    name = ""
    if rec.exists():
        try:
            name = json.loads(rec.read_text(encoding="utf-8")).get("video", "")
        except Exception:
            name = ""
    dest = videos_dir(cfg) / name if name else free_name(videos_dir(cfg), made.stem)
    dest.parent.mkdir(parents=True, exist_ok=True)
    made.replace(dest)
    rec.write_text(json.dumps({"video": dest.name}, ensure_ascii=False), encoding="utf-8")
    return dest


def _log(msg: str) -> None:
    print(msg, flush=True)


# --- plan ---------------------------------------------------------------------

PLAN_VERSION = 1      # bump when make_plan's output changes, so saved plans are made again


def demo_stem(path: str | Path) -> str:
    """'match.dem.zst' -> 'match' (the name the unpacked demo and its jobs use)."""
    name = Path(path).name
    for suffix in (".zst", ".gz", ".bz2"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
    return name[:-4] if name.lower().endswith(".dem") else Path(name).stem


def _source_record(cfg: Config, source: Path, player_query: str, rounds, suffix: str, trim) -> dict:
    st = source.stat()
    return {"demo": str(source.resolve()), "mtime": st.st_mtime, "size": st.st_size, "player": player_query,
            "rounds": sorted(rounds) if rounds else None, "suffix": suffix,
            "trim": list(trim) if trim else None, "plan_options": asdict(cfg.plan), "v": PLAN_VERSION}


def job_roots(cfg: Config) -> list[Path]:
    """Where jobs live: the work folder, and the output folder itself (older versions)."""
    return [work_root(cfg), cfg.output_dir]


def saved_plan(cfg: Config, record: dict) -> Path | None:
    """A job whose plan was made from exactly this demo, player and choice of rounds."""
    root = work_root(cfg)
    if not root.is_dir():
        return None
    for f in root.glob("*/source.json"):
        try:
            if json.loads(f.read_text(encoding="utf-8")) == record:
                job = f.parent
                if all((job / n).exists() for n in ("plan.json", "kills.json", "positions.pkl", "keys.pkl")):
                    return job
        except Exception:
            continue
    return None


def whole_match_job(cfg: Config, demo: str | Path, steamid: str) -> Path | None:
    """The whole-match job (not a reel) of this demo and player, if one was planned."""
    stem = demo_stem(demo)
    for root in job_roots(cfg):
        if not root.is_dir():
            continue
        for f in root.glob("*/plan.json"):
            if f.parent.name.endswith("__reel"):
                continue
            try:
                plan = load_plan(f.parent)
            except Exception:
                continue
            if plan.player.steamid == steamid and Path(plan.demo_path).stem == stem:
                return f.parent
    return None


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
              rounds: set[int] | None = None, job_suffix: str = "",
              trim_to_kills: tuple[float, float] | None = None) -> tuple[Plan, Path]:
    """Work out the clips to record. ``job_suffix`` keeps a separate job folder
    (the highlight reel uses its own); ``trim_to_kills`` = (seconds before the
    first kill, seconds after the last) records only that part of each round."""
    source = Path(demo_path)
    record = _source_record(cfg, source, player_query, rounds, job_suffix, trim_to_kills)
    known = saved_plan(cfg, record)
    if known is not None:                      # read before: skip reading the demo again
        plan = load_plan(known)
        _log(f"Using the earlier reading of {source.name} ({len(plan.segments)} clips)")
        return plan, known
    demo_path = prepare_demo(demo_path, work_root(cfg) / "demos")
    _log(f"Reading {demo_path.name} ...")
    demo = load_demo(demo_path)
    player = find_player(demo.players, player_query)
    job = job_dir_for(cfg, demo_path, player.name, job_suffix)
    job.mkdir(parents=True, exist_ok=True)

    _log(f"Parsing positions and inputs for {player.name} ...")
    pos, keys = load_ticks(demo_path, player.steamid)
    pos.to_pickle(job / "positions.pkl")
    keys.to_pickle(job / "keys.pkl")
    load_hud(demo_path, player.steamid).to_pickle(job / "hud.pkl")
    with open(job / "utility.pkl", "wb") as f:
        pickle.dump(load_utility(demo_path), f)
    track = Track(pos, keys)
    kills = [[d.tick, d.headshot] for d in demo.deaths
             if d.attacker_steamid == player.steamid and d.victim_steamid != player.steamid]
    (job / "kills.json").write_text(json.dumps(kills), encoding="utf-8")
    highlights.save(job / "highlights.json", highlights.analyse(demo, player.steamid, track))
    try:
        teams = load_scoreboard(demo_path, len(demo.rounds))
    except Exception as e:  # scoreboard is only for the intro card
        _log(f"Note: no scoreboard for the intro ({e})")
        teams = []
    date = datetime.date.fromtimestamp(source.stat().st_mtime).isoformat()
    meta = {"date": date, "faceit_match": faceit.match_id(source.name),
            "teams": [asdict(t) for t in teams]}
    (job / "meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    segments = plan_segments(
        demo.rounds, demo.deaths, player.steamid, demo.tickrate, demo.last_tick,
        cfg.plan, alive_at=lambda t: track.alive_at(player.steamid, t),
    )
    if rounds:
        segments = [sg for sg in segments if sg.round_number in rounds]
    if trim_to_kills:
        segments = trim_segments(segments, [t for t, _ in kills], demo.tickrate, *trim_to_kills)
    plan = Plan(str(demo_path.resolve()), demo.map_name, demo.tickrate, player, segments)
    plan_file = job / "plan.json"
    if plan_file.exists() and load_plan(job).segments != plan.segments:
        renumber_clips(job, load_plan(job).segments, plan.segments)
    plan_file.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
    (job / "source.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")

    mins = plan.total_seconds() / 60
    _log(f"{demo.map_name}: {len(demo.rounds)} rounds, {player.name} played {len(segments)}; "
         f"video length about {mins:.1f} min")
    if not track.has_keys:
        _log("Note: this demo has no input data, the keyboard overlay will stay blank.")
    return plan, job


def trim_segments(segments: list[Segment], kill_ticks: list[int], tickrate: float,
                  before: float, after: float, pad: float = 1.0) -> list[Segment]:
    """Shorten each round to its kills (plus a little room); rounds without
    kills (a clutch won on the bomb) are kept whole."""
    out = []
    for sg in segments:
        ks = sorted(t for t in kill_ticks if sg.start_tick <= t <= sg.end_tick)
        if ks:
            a = max(sg.start_tick, ks[0] - round((before + pad) * tickrate))
            b = min(sg.end_tick, ks[-1] + round((after + pad) * tickrate))
            sg = Segment(sg.round_number, a, b, sg.ends_by)
        out.append(sg)
    return out


def renumber_clips(job: Path, old: list[Segment], new: list[Segment]) -> None:
    """The clip list changed (other rounds chosen). Clips are numbered by
    position, so move every recorded clip whose round is still wanted, unchanged,
    to its new number; drop the rest. Composed parts are made again (overlays
    are kept: they're named by round)."""
    clips = job / "clips"
    keep = {}
    for i, seg in enumerate(old):
        f = clips / f"clip_{i:03d}.mp4"
        if f.exists() and seg in new:
            tmp = clips / f"keep_{seg.round_number:03d}_{i:03d}.mp4"
            f.replace(tmp)
            keep[seg] = tmp
    for f in clips.glob("clip_*.mp4"):
        f.unlink()
    for i, seg in enumerate(new):
        if seg in keep:
            keep.pop(seg).replace(clips / f"clip_{i:03d}.mp4")
    for f in keep.values():
        f.unlink()
    for f in (job / "parts").glob("*.mp4"):
        f.unlink()


def load_plan(job: Path) -> Plan:
    plan = Plan.from_dict(json.loads((job / "plan.json").read_text(encoding="utf-8")))
    if not Path(plan.demo_path).exists():
        # the work folder was moved (e.g. when videos were sorted by player): the
        # unpacked demo is in the "demos" folder next to this job
        moved = job.parent / "demos" / Path(plan.demo_path).name
        if moved.exists():
            plan.demo_path = str(moved.resolve())
    return plan


def load_track(job: Path) -> Track:
    hud = pd.read_pickle(job / "hud.pkl") if (job / "hud.pkl").exists() else None
    utility = None
    if (job / "utility.pkl").exists():
        with open(job / "utility.pkl", "rb") as f:
            utility = pickle.load(f)
    return Track(pd.read_pickle(job / "positions.pkl"), pd.read_pickle(job / "keys.pkl"), hud, utility)


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
                                      place_label=o.place_label, show_utility=o.utility)
        except RuntimeError as e:
            _log(f"Minimap disabled: {e}")
    if o.keyboard:
        keyboard = KeyboardRenderer(scale=o.keyboard_scale * scale)
    if o.hud and cfg.record.game_hud == "killfeed":
        hud = HudRenderer(cfg.record.width, scale)
    elif o.player_bar and cfg.record.game_hud == "full":
        hud = PlayerBarRenderer(scale)
    return minimap, keyboard, hud


def static_images(cfg: Config, job: Path) -> dict[str, Path]:
    """Crosshair and scope PNGs, drawn once per job."""
    out_dir = job / "overlays"
    out_dir.mkdir(parents=True, exist_ok=True)
    scale = cfg.record.height / 1080
    imgs = {}
    if cfg.record.game_hud != "killfeed":
        return imgs  # the game draws its own crosshair and scope
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
    kf = job / "kills.json"
    kills = [(int(t), bool(hs)) for t, hs in json.loads(kf.read_text())] if kf.exists() else []
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
        stamp = f"{start}+{frames}@{cfg.record.fps}/{cfg.record.height} {cfg.overlay} {cfg.record.game_hud} v3"
        if done.exists() and done.read_text() == stamp:
            layers = {k: Path(f"{stem}_{k}.mov") for k in ("minimap", "keyboard", "hud")
                      if Path(f"{stem}_{k}.mov").exists()}
            layers["static"] = Path(f"{stem}_static.json")
        else:
            _log(f"Overlays {i + 1}/{len(plan.segments)} (round {seg.round_number})")
            layers = render_segment(plan, seg, track, out_dir, cfg.record.fps, minimap, keyboard,
                                    cfg.overlay.sync_offset_frames, cfg.compose.ffmpeg,
                                    start_tick=start, frames=frames, hud=hud, kills=kills)
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
    out = job / "parts" / "intro.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    if c.image.strip().lower() == "auto":
        image = faceit_screenshot(cfg, job, meta.get("faceit_match") or faceit.match_id(plan.demo_path))
    else:
        image = resolve_intro_image(c.image)
    fields["date"] = c.date or intro_date(cfg, job, meta)
    info = IntroInfo(c.title.format(**fields), c.subtitle.format(**fields), plan.player.steamid, teams)
    _log("Making intro" + (f" from {image.name}" if image else "") + " ...")
    return make_intro(info, out, (cfg.record.width, cfg.record.height), cfg.record.fps, c.seconds,
                      cfg.compose, clips[0] if clips else None, screenshot=image)


def intro_date(cfg: Config, job: Path, meta: dict) -> str:
    """FACEIT match start in local time if known, else the demo file's date."""
    f = job / "faceit_match.json"
    if f.exists():
        try:
            t = faceit.match_time(json.loads(f.read_text(encoding="utf-8")), cfg.intro.timezone)
            if t is not None:
                return t.strftime(cfg.intro.date_format)
        except Exception as e:
            _log(f"Note: could not read the match time ({e})")
    return meta.get("date", "")


def faceit_screenshot(cfg: Config, job: Path, mid: str | None) -> Path | None:
    """Screenshot of the FACEIT match room (kept for later runs); None if not possible."""
    if not mid:
        return None
    shot, info = job / "faceit_room.png", job / "faceit_match.json"
    if shot.exists() and info.exists():
        return shot
    _log(f"Taking a screenshot of the FACEIT match room {mid} ...")
    try:
        return faceit.screenshot_room(mid, shot, (cfg.record.width, cfg.record.height),
                                      headless=not cfg.intro.show_browser, info_out=info)
    except Exception as e:
        _log(f"Note: FACEIT screenshot failed, using the scoreboard card instead ({e})")
        return None


IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def resolve_intro_image(spec: str) -> Path | None:
    """'' = none; 'latest' = newest image in Pictures\\Screenshots; otherwise a file path."""
    if not spec:
        return None
    if spec.lower() == "latest":
        folders = [Path.home() / "Pictures" / "Screenshots", Path.home() / "OneDrive" / "Pictures" / "Screenshots",
                   Path.home() / "Pictures" / "屏幕截图"]
        found = [f for d in folders if d.is_dir() for f in d.iterdir() if f.suffix.lower() in IMAGE_TYPES]
        if not found:
            raise RuntimeError("No screenshot found in Pictures\\Screenshots. Give the image path instead.")
        return max(found, key=lambda f: f.stat().st_mtime)
    p = Path(spec).expanduser()
    if not p.is_file():
        raise RuntimeError(f"Intro image not found: {p}")
    return p


def make_video(cfg: Config, job: Path, clips: list[Path]) -> Path:
    layers = make_overlays(cfg, job, clips)
    intro = make_intro_clip(cfg, job, clips)
    plan = load_plan(job)
    hl = highlights.load(job / "highlights.json")
    titles = {sg.round_number: highlights.chapter_title(sg.round_number, hl.get(sg.round_number),
                                                         cfg.compose.chapter_lang)
              for sg in plan.segments}
    final = compose(plan, job, clips, layers, cfg.record.fps, cfg.compose,
                    size=(cfg.record.width, cfg.record.height), intro=intro,
                    static_images=static_images(cfg, job), titles=titles)
    final = publish(cfg, job, final)
    make_extras(cfg, job, plan, clips, final, intro)
    make_upload_copy(cfg, final)
    return final


def make_upload_copy(cfg: Config, final: Path) -> None:
    """The scaled-up copy for uploading, if asked for; a failure never loses the video."""
    if not cfg.upload.upscale:
        return
    from .compose import upload_copy
    try:
        upload_copy(final, cfg.upload.upscale, cfg.compose, _log)
    except Exception as e:
        _log(f"Note: upload copy failed ({e})")


def make_extras(cfg: Config, job: Path, plan: Plan, clips: list[Path], final: Path,
                intro: Path | None) -> None:
    """Highlight cut and upload kit; a failure here never loses the main video."""
    from . import extras
    if cfg.highlights.enabled:
        try:
            _log("Cutting the highlights ...")
            parts = [job / "parts" / f"part_{i:03d}.mp4" for i in range(len(plan.segments))]
            hv = extras.make_highlight_video(cfg, job, plan, parts, intro)
            if hv:
                _log(f"Highlights: {hv.resolve()}")
            else:
                _log("Note: no kills in the recorded rounds, so no highlight video.")
        except Exception as e:
            _log(f"Note: highlight video failed ({e})")
    if cfg.upload.enabled:
        try:
            _log("Making the cover and description ...")
            cover, desc = extras.make_upload_kit(cfg, job, plan, clips, final,
                                                 cfg.intro.date or intro_date(cfg, job, load_meta(job)))
            # next to the video, with the same name: video.mp4, video.jpg, video.txt
            import shutil
            cover = Path(shutil.copyfile(cover, final.with_suffix(".jpg")))
            desc = Path(shutil.copyfile(desc, final.with_suffix(".txt")))
            _log(f"Cover: {cover.resolve()}")
            _log(f"Description: {desc.resolve()}")
        except Exception as e:
            _log(f"Note: cover/description failed ({e})")


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
