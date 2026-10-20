"""Command line: ``povforge <command> ...``"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import load_config


def _cmd_inspect(args, cfg) -> None:
    if args.json:                       # what the app reads (it runs this in a child process)
        import json
        from .gui.server import inspect_demo
        print(json.dumps(inspect_demo(args.demo, Path(args.work or cfg.output_dir)), ensure_ascii=False), flush=True)
        return
    from .demo import load_demo, prepare_demo

    from .pipeline import work_root
    d = load_demo(prepare_demo(args.demo, work_root(cfg) / "demos"))
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

    if args.intro_image is not None:
        cfg.intro.image = args.intro_image
    job = Path(args.job)
    clips = make_recording(cfg, job, placeholder=args.placeholder)
    print(make_video(cfg, job, clips))


def _cmd_run(args, cfg) -> None:
    from .pipeline import parse_rounds, run

    if args.intro_image is not None:
        cfg.intro.image = args.intro_image
    run(cfg, args.demo, args.player, placeholder=args.placeholder, rounds=parse_rounds(args.rounds))


def _cmd_reel(args, cfg) -> None:
    from . import reel

    title, items = reel.load_spec(Path(args.spec))
    reel.run(cfg, args.title or title, items, placeholder=args.placeholder, fx=reel.load_effects(Path(args.spec)))


def _cmd_analyze_style(args, cfg) -> None:
    """Work out a finished video's effects (what the app's "copy a video's style" does)."""
    import json
    from . import style
    if args.json:
        print(json.dumps(style.analyze(args.video, cfg.compose.ffmpeg), ensure_ascii=False), flush=True)
        return
    r = style.analyze(args.video, cfg.compose.ffmpeg)
    v = r["video"]
    print(f"{Path(args.video).name}: {v['seconds']} s, {v['width']}x{v['height']}, {v['fps']} fps")
    for line in r["report"]:
        print("  " + ", ".join(f"{k}={val}" for k, val in line.items()))
    print("Effects: " + json.dumps(r["effects"], ensure_ascii=False))


def _cmd_self_update(args, cfg) -> None:
    """Bring an install up to date from a release zip (what the app's update does;
    also used to test it). --manifest only writes the file list of a build."""
    import json
    import tempfile
    from . import selfupdate
    app = Path(args.app).resolve()
    if args.manifest:
        m = selfupdate.make_manifest(app, __version__)
        (app / selfupdate.MANIFEST).write_text(json.dumps(m, indent=0), encoding="utf-8")
        print(f"Wrote {app / selfupdate.MANIFEST}: {len(m['files'])} files")
        return
    work = Path(tempfile.mkdtemp(prefix="povforge-update-"))
    plan = selfupdate.prepare(app, args.zip, args.current or __version__, work,
                              lambda d, t: print(f"  {d >> 20}/{t >> 20} MB", flush=True))
    print(f"To fetch: {plan['changed']}; to remove: {plan['removed']}", flush=True)
    code = selfupdate.apply(app, work, plan, Path(args.log or work.parent / "povforge-update.log"),
                            relaunch=False, wait=True)
    if code != 0:
        raise RuntimeError(f"applying the update failed (exit {code})")
    z, _ = selfupdate.open_zip(args.zip)
    want = json.loads(z.read("PovForge/" + selfupdate.MANIFEST))["files"]
    got = selfupdate.make_manifest(app, "")["files"]
    if got != want:
        bad = [p for p in set(got) | set(want) if got.get(p) != want.get(p)][:5]
        raise RuntimeError(f"after the update these files differ from the release: {bad}")
    print("Update applied; every file matches the release.")


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
    try:  # demoparser2 also needs polars and pyarrow at run time to hand back tables
        for mod in ("demoparser2", "polars", "pyarrow"):
            importlib.import_module(mod)
        line(True, "demoparser2", "with polars and pyarrow")
    except ImportError as e:
        line(False, "demoparser2", f"{e} (pip install demoparser2 polars pyarrow)")
    try:
        from .cdp import find_browser
        browser = find_browser()
        if browser is None:
            raise ImportError
        line(True, "Browser", f"{browser} (FACEIT intro screenshot)")
    except ImportError:
        line(False, "Browser", "no Edge or Chrome found (needed for the FACEIT intro screenshot)", warn=True)
    from .media import ffprobe_for
    for tool in (cfg.compose.ffmpeg, ffprobe_for(cfg.compose.ffmpeg)):
        found = shutil.which(tool)
        line(bool(found), Path(tool).stem, found or "missing: run povforge setup")
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
    from . import settings_guard
    line(not settings_guard.pending(), "CS2 settings",
         "unchanged" if not settings_guard.pending() else "backup not restored yet: run povforge restore-settings")
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


def _cmd_gui(args, cfg) -> None:
    from .app import hide_console_windows
    from .gui.server import main as gui_main
    hide_console_windows()
    gui_main(port=args.port, open_browser=not args.no_window)


def _cmd_setup(args, cfg) -> None:
    """Download HLAE and FFmpeg if they're missing."""
    from . import hlae, tools

    def show(msg: str, frac: float) -> None:
        pct = f" {frac * 100:3.0f}%" if frac >= 0 else ""
        print(f"\r  {msg}{pct}   ", end="", flush=True)

    try:
        print(f"HLAE: {hlae.find_hlae(cfg.record)}")
    except RuntimeError:
        print("HLAE: downloading ...")
        print(f"\r  installed: {tools.install_hlae(show)}            ")
    ff = tools.find_ffmpeg(cfg.compose.ffmpeg)
    if ff and not args.force:
        print(f"FFmpeg: {ff}")
    else:
        print("FFmpeg: downloading ...")
        print(f"\r  installed: {tools.install_ffmpeg(show)}            ")
    print("Ready. Check everything with: povforge doctor")


def _cmd_restore_settings(args, cfg) -> None:
    from . import hlae, settings_guard

    if not settings_guard.pending():
        print("Nothing to restore: your CS2 settings are as they were.")
        return
    if "cs2.exe" in hlae.running_processes():
        raise RuntimeError("Close CS2 first, then run this again.")
    n = settings_guard.restore()
    if settings_guard.pending():
        raise RuntimeError(f"Some files could not be restored. The backup is kept in {settings_guard.guard_dir()}")
    print(f"Your CS2 settings are back as before ({n} file(s) put back).")


def _restore_leftover_settings() -> None:
    """A recording that was cut off may have left the backup unrestored."""
    from . import hlae, settings_guard

    if not settings_guard.pending() or "cs2.exe" in hlae.running_processes():
        return
    try:
        n = settings_guard.restore()
        print(f"Restored your CS2 settings left over from an interrupted recording ({n} file(s)).")
    except Exception as e:
        print(f"Warning: could not restore your CS2 settings ({e}). Run: povforge restore-settings")


def _cmd_faceit(args, cfg) -> None:
    from pathlib import Path

    from . import faceit

    mid = faceit.match_id(args.demo)
    if not mid:
        raise RuntimeError(f"No FACEIT match id (1-xxxxxxxx-...) in '{args.demo}'")
    out = Path(args.out or f"faceit_{mid}.png").resolve()
    print(f"Opening {faceit.room_url(mid)} ...", flush=True)
    faceit.screenshot_room(mid, out, (cfg.record.width, cfg.record.height),
                           headless=not (args.show or cfg.intro.show_browser))
    print(f"Saved {out}")


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
    s.add_argument("--json", action="store_true", help="everything the app shows, as one JSON line")
    s.add_argument("--work", help="output folder (with --json)")
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
        s.add_argument("--intro-image", help="intro background: 'auto', 'latest', a file, or '' "
                                             "(compose only)")
        s.set_defaults(func=func)

    s = sub.add_parser("run", help="plan, render overlays, record and compose in one go")
    s.add_argument("demo")
    s.add_argument("player", help="player name (or part of it) or steamid")
    s.add_argument("--placeholder", action="store_true",
                   help="use grey test clips instead of recording (no CS2 needed)")
    s.add_argument("--rounds", help="only these rounds, e.g. 1-3,7 (handy for a quick test)")
    s.add_argument("--intro-image", help="intro background: 'auto' (default: FACEIT match room, "
                                         "screenshotted automatically), 'latest', a file, or '' for "
                                         "the scoreboard card")
    s.set_defaults(func=_cmd_run)

    s = sub.add_parser("reel", help="highlight reel: the kills of chosen rounds, from one or more demos")
    s.add_argument("spec", help='JSON file: {"title": "...", "items": [{"demo": path, "steamid": id, "round": n}, ...]}')
    s.add_argument("--title", help="file name for the reel (default: the title in the spec)")
    s.add_argument("--placeholder", action="store_true", help="grey test clips instead of recording in CS2")
    s.set_defaults(func=_cmd_reel)

    s = sub.add_parser("analyze-style", help="work out the effects of a finished highlight video")
    s.add_argument("video")
    s.add_argument("--json", action="store_true", help="print the result as JSON")
    s.set_defaults(func=_cmd_analyze_style)

    s = sub.add_parser("self-update", help="update an install from a release zip (or write a build's file list)")
    s.add_argument("--app", required=True, help="the PovForge folder")
    s.add_argument("--zip", help="PovForge-windows.zip (path or URL)")
    s.add_argument("--current", help="the installed version (default: this one)")
    s.add_argument("--log", help="log file")
    s.add_argument("--manifest", action="store_true", help="only write manifest.json for the folder")
    s.set_defaults(func=_cmd_self_update)

    s = sub.add_parser("doctor", help="check that everything needed is installed")
    s.set_defaults(func=_cmd_doctor)

    s = sub.add_parser("maps", help="download or refresh radar images")
    s.add_argument("names", nargs="+", help="map names, e.g. de_dust2 de_mirage")
    s.set_defaults(func=_cmd_maps)

    s = sub.add_parser("gui", help="open the PovForge app window")
    s.add_argument("--port", type=int, default=0, help=argparse.SUPPRESS)
    s.add_argument("--no-window", action="store_true", help="only start the server")
    s.set_defaults(func=_cmd_gui)

    s = sub.add_parser("setup", help="download HLAE and FFmpeg if they're missing")
    s.add_argument("--force", action="store_true", help="download FFmpeg even if one is found")
    s.set_defaults(func=_cmd_setup)

    s = sub.add_parser("restore-settings", help="put your CS2 settings back (normally automatic)")
    s.set_defaults(func=_cmd_restore_settings)

    s = sub.add_parser("faceit", help="screenshot a FACEIT match room (what the intro uses)")
    s.add_argument("demo", help="FACEIT demo file name, or the match id")
    s.add_argument("--out", help="image file (default: faceit_<match id>.png here)")
    s.add_argument("--show", action="store_true", help="show the browser window")
    s.set_defaults(func=_cmd_faceit)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        # Only before recording: a read-only command (the app reading a demo, say)
        # may run while a recording has just backed the settings up and is starting
        # CS2, and must not put them back under it.
        if args.func in (_cmd_run, _cmd_record, _cmd_reel):
            _restore_leftover_settings()
        cfg = load_config(args.config)
        from . import tools
        cfg.compose.ffmpeg = tools.find_ffmpeg(cfg.compose.ffmpeg) or cfg.compose.ffmpeg
        args.func(args, cfg)
    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
