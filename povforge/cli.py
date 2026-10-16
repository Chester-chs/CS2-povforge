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
    from .pipeline import make_overlays

    make_overlays(cfg, Path(args.job))


def _cmd_record(args, cfg) -> None:
    from .pipeline import make_recording

    make_recording(cfg, Path(args.job), placeholder=args.placeholder)


def _cmd_compose(args, cfg) -> None:
    from .compose import compose
    from .pipeline import load_plan, make_overlays, make_recording

    job = Path(args.job)
    layers = make_overlays(cfg, job)
    clips = make_recording(cfg, job, placeholder=args.placeholder)
    print(compose(load_plan(job), job, clips, layers, cfg.record.fps, cfg.compose))


def _cmd_run(args, cfg) -> None:
    from .pipeline import parse_rounds, run

    run(cfg, args.demo, args.player, placeholder=args.placeholder, rounds=parse_rounds(args.rounds))


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

    s = sub.add_parser("overlays", help="render minimap and keyboard layers for a planned job")
    s.add_argument("job", help="job folder created by 'plan'")
    s.set_defaults(func=_cmd_overlays)

    for name, func, helptext in (
        ("record", _cmd_record, "record the planned clips in CS2 (via CSVG)"),
        ("compose", _cmd_compose, "add overlays and join clips into the final video"),
    ):
        s = sub.add_parser(name, help=helptext)
        s.add_argument("job", help="job folder created by 'plan'")
        s.add_argument("--placeholder", action="store_true",
                       help="use grey test clips instead of recording (no CS2 needed)")
        s.set_defaults(func=func)

    s = sub.add_parser("run", help="plan, render overlays, record and compose in one go")
    s.add_argument("demo")
    s.add_argument("player", help="player name (or part of it) or steamid")
    s.add_argument("--placeholder", action="store_true",
                   help="use grey test clips instead of recording (no CS2 needed)")
    s.add_argument("--rounds", help="only these rounds, e.g. 1-3,7 (handy for a quick test)")
    s.set_defaults(func=_cmd_run)

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
