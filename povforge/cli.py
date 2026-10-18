"""Command line: ``povforge <command> ...``"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import load_config


def _cmd_inspect(args, cfg) -> None:
    from .demo import load_demo, prepare_demo

    d = load_demo(prepare_demo(args.demo, cfg.output_dir / "demos"))
    print(f"Map: {d.map_name}   Rounds: {len(d.rounds)}   Length: {d.last_tick / d.tickrate / 60:.1f} min")
    print("Players:")
    for p in d.players:
        print(f"  {p.name:<24} {p.steamid}")


def _cmd_plan(args, cfg) -> None:
    from .pipeline import make_plan, parse_rounds

    plan, job = make_plan(cfg, args.demo, args.player, parse_rounds(args.rounds))
    for s in plan.segments:
        print(f"  round {s.round_number:>2}  ticks {s.start_tick}-{s.end_tick}  "
              f"{s.duration_seconds(plan.tickrate):5.1f}s  ends by {s.ends_by}")
    print(f"Job folder: {job}")


def _cmd_overlays(args, cfg) -> None:
    from .pipeline import load_plan, make_overlays

    job = Path(args.job)
    clips = [job / "clips" / f"clip_{i:03d}.mp4" for i in range(len(load_plan(job).segments))]
    make_overlays(cfg, job, clips)


def _cmd_record(args, cfg) -> None:
    from .pipeline import make_recording

    make_recording(cfg, Path(args.job), placeholder=args.placeholder)


def _cmd_compose(args, cfg) -> None:
    from .pipeline import make_recording, make_video

    if args.intro_image:
        cfg.intro.image = args.intro_image
    job = Path(args.job)
    clips = make_recording(cfg, job, placeholder=args.placeholder)
    print(make_video(cfg, job, clips))


def _cmd_run(args, cfg) -> None:
    from .pipeline import parse_rounds, run

    if args.intro_image:
        cfg.intro.image = args.intro_image
    run(cfg, args.demo, args.player, placeholder=args.placeholder, rounds=parse_rounds(args.rounds))


def _cmd_doctor(args, cfg) -> None:
    import importlib
    import shutil

    from . import hlae

    ok = True

    def line(good: bool, what: str, detail: str = "", warn: bool = False) -> None:
        nonlocal ok
        mark = "OK  " if good else ("WARN" if warn else "FAIL")
        if not good and not warn:
            ok = False
        print(f"[{mark}] {what}" + (f": {detail}" if detail else ""))

    line(sys.version_info >= (3, 11), "Python", sys.version.split()[0])
    try:
        importlib.import_module("demoparser2")
        line(True, "demoparser2")
    except ImportError:
        line(False, "demoparser2", "pip install demoparser2")
    for tool in (cfg.compose.ffmpeg, "ffprobe"):
        found = shutil.which(tool)
        line(bool(found), tool, found or "not on PATH")
    if sys.platform != "win32":
        line(False, "Windows", "recording needs Windows; --placeholder works anywhere", warn=True)
        print("\nAll good." if ok else "\nFix the FAIL lines above.")
        return
    try:
        h = hlae.find_hlae(cfg.record)
        dll = h.parent / "x64" / "AfxHookSource2.dll"
        line(dll.is_file(), "HLAE", str(h) if dll.is_file() else f"{dll} missing")
    except RuntimeError as e:
        line(False, "HLAE", str(e))
    try:
        line(True, "CS2", str(hlae.find_cs2(cfg.record)))
    except RuntimeError as e:
        line(False, "CS2", str(e))
    procs = hlae.running_processes()
    line("steam.exe" in procs, "Steam running", "" if "steam.exe" in procs else "start Steam before recording",
         warn=True)
    line("cs2.exe" not in procs, "CS2 closed", "" if "cs2.exe" not in procs else "close CS2 before recording",
         warn=True)
    for exe, name in hlae.ANTI_CHEAT.items():
        if exe in procs:
            line(False, f"{name} running", "close it before recording", warn=True)
    print("\nAll good." if ok else "\nFix the FAIL lines above.")


def _cmd_maps(args, cfg) -> None:
    from .maps import cache_dir, get_map

    for name in args.names:
        a = get_map(name, refresh=True)
        print(f"{name}: ok{' (+ lower level)' if a.radar_lower else ''}")
    print(f"Cached in {cache_dir()}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="povforge",
        description="Turn CS2 demos into full-match POV videos of one player.",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument("-c", "--config", help="settings file (default: ./povforge.toml if present)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("inspect", help="show map, rounds and players of a demo")
    s.add_argument("demo")
    s.set_defaults(func=_cmd_inspect)

    s = sub.add_parser("plan", help="work out which parts of each round to record")
    s.add_argument("demo")
    s.add_argument("player", help="player name (or part of it) or steamid")
    s.add_argument("--rounds", help="only these rounds, e.g. 1-3,7 (handy for a quick test)")
    s.set_defaults(func=_cmd_plan)

    s = sub.add_parser("overlays", help="render minimap and keyboard layers for a job")
    s.add_argument("job", help="job folder created by 'plan'")
    s.set_defaults(func=_cmd_overlays)

    for name, func, helptext in (
        ("record", _cmd_record, "record the planned clips in CS2 (via HLAE)"),
        ("compose", _cmd_compose, "add overlays and join clips into the final video"),
    ):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("job", help="job folder created by 'plan'")
        s.add_argument("--placeholder", action="store_true",
                       help="use grey test clips instead of recording (no CS2 needed)")
        s.add_argument("--intro-image", help="screenshot for the intro, or 'latest' (compose only)")
        s.set_defaults(func=func)

    s = sub.add_parser("run", help="plan, render overlays, record and compose in one go")
    s.add_argument("demo")
    s.add_argument("player", help="player name (or part of it) or steamid")
    s.add_argument("--placeholder", action="store_true",
                   help="use grey test clips instead of recording (no CS2 needed)")
    s.add_argument("--rounds", help="only these rounds, e.g. 1-3,7 (handy for a quick test)")
    s.add_argument("--intro-image", help="screenshot for the intro (e.g. the FACEIT match room), "
                                         "or 'latest' for your newest screenshot")
    s.set_defaults(func=_cmd_run)

    s = sub.add_parser("doctor", help="check that everything needed is installed")
    s.set_defaults(func=_cmd_doctor)

    s = sub.add_parser("maps", help="download or refresh radar images")
    s.add_argument("names", nargs="+", help="map names, e.g. de_dust2 de_mirage")
    s.set_defaults(func=_cmd_maps)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        cfg = load_config(args.config)
        args.func(args, cfg)
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
