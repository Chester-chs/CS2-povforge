"""Recording backend: CS2 played through HLAE.

HLAE (Half-Life Advanced Effects, https://github.com/advancedfx/advancedfx,
MIT) is installed separately by the user. We launch CS2 through it, load our
director script (director.js) with HLAE's ``mirv_script_load``, and HLAE's
``mirv_streams`` renders each clip offline at a fixed frame rate.

The launch options and console settings follow what CS Demo Manager
(https://github.com/akiver/cs-demo-manager, MIT) does for CS2; no code is
copied from either project.

CS2 runs with -insecure (VAC off) for the session. Never join online servers
while it runs.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from .maps import parse_keyvalues
from .model import Plan, Segment

CFG_NAME = "povforge_job"


@dataclass
class RecordSettings:
    width: int = 1920
    height: int = 1080
    fps: int = 60
    hlae_path: str = ""          # empty = look in the usual places
    cs2_path: str = ""           # cs2.exe; empty = find it through Steam
    window_mode: str = "windowed"  # windowed | fullscreen
    video_options: str = "-c:v libx264 -pix_fmt yuv420p -preset veryfast -crf 16"
    preroll_seconds: float = 2.0  # time spent at the clip start before recording
    spec_mode: str = ""           # optional spec_mode value, if a CS2 update needs it
    hide_demo_ui: bool = True     # toggle off CS2's demo playback bar once the demo starts
    extra_setup: str = ""         # extra console commands, separated by ;
    timeout_factor: float = 3.0   # give up after this many times the video length (+10 min)


# --- finding things -------------------------------------------------------------

def find_hlae(s: RecordSettings) -> Path:
    candidates = []
    if s.hlae_path:
        candidates.append(Path(s.hlae_path))
    on_path = shutil.which("HLAE")
    if on_path:
        candidates.append(Path(on_path))
    local = os.environ.get("LOCALAPPDATA", "")
    candidates += [
        Path("C:/Tools/hlae/HLAE.exe"),
        Path("C:/hlae/HLAE.exe"),
        Path(local) / "HLAE" / "HLAE.exe" if local else None,
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "HLAE" / "HLAE.exe",
    ]
    for c in candidates:
        if c is not None and c.is_file():
            return c
    raise RuntimeError(
        "HLAE not found. Download it from https://github.com/advancedfx/advancedfx/releases, "
        "unzip it to C:\\Tools\\hlae, or set [record] hlae_path in povforge.toml."
    )


def _steam_dir() -> Path | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            return Path(winreg.QueryValueEx(k, "SteamPath")[0])
    except OSError:
        return None


def steam_libraries(steam_dir: Path) -> list[Path]:
    vdf = steam_dir / "steamapps" / "libraryfolders.vdf"
    libs = [steam_dir]
    if vdf.is_file():
        kv = parse_keyvalues(vdf.read_text(encoding="utf-8", errors="replace"))
        root = kv.get("libraryfolders", kv)
        for entry in root.values():
            if isinstance(entry, dict) and "path" in entry:
                libs.append(Path(entry["path"].replace("\\\\", "\\")))
    return libs


def find_cs2(s: RecordSettings) -> Path:
    if s.cs2_path:
        p = Path(s.cs2_path)
        if p.is_file():
            return p
        raise RuntimeError(f"cs2_path does not exist: {p}")
    rel = Path("steamapps/common/Counter-Strike Global Offensive/game/bin/win64/cs2.exe")
    steam = _steam_dir()
    libs = steam_libraries(steam) if steam else []
    for drive in "CDEFG":
        libs += [Path(f"{drive}:/SteamLibrary"), Path(f"{drive}:/Steam"),
                 Path(f"{drive}:/Program Files (x86)/Steam")]
    for lib in libs:
        exe = lib / rel
        if exe.is_file():
            return exe
    raise RuntimeError("CS2 not found. Set [record] cs2_path in povforge.toml to your cs2.exe.")


def csgo_dir(cs2_exe: Path) -> Path:
    """.../game/bin/win64/cs2.exe -> .../game/csgo"""
    return cs2_exe.parents[2] / "csgo"


def running_processes() -> set[str]:
    if sys.platform != "win32":
        return set()
    out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True,
                         errors="replace").stdout
    return {line.split('","')[0].strip('"').lower() for line in out.splitlines() if line}


ANTI_CHEAT = {"faceit.exe": "FACEIT", "faceitclient.exe": "FACEIT", "faceitservice.exe": "FACEIT AC",
              "5eclient.exe": "5E", "perfectworldarena.exe": "完美世界"}


# --- job files ------------------------------------------------------------------

def clip_id(seg: Segment) -> str:
    return f"r{seg.round_number:02d}"


def setup_commands(s: RecordSettings) -> list[str]:
    cmds = [
        "sv_cheats 1",
        "demo_timescale 1",
        "cl_draw_only_deathnotices 0",
        "spec_show_xray 0",
        "mp_display_kill_assists 1",
        "cl_demo_predict 1",
        "r_show_build_info 0",
        "cl_trueview_show_status 0",
        "cl_hud_telemetry_frametime_show 0",
        "cl_hud_telemetry_net_misdelivery_show 0",
        "cl_hud_telemetry_ping_show 0",
        "cl_hud_telemetry_serverrecvmargin_graph_show 0",
        "mirv_streams record screen enabled 1",
        f'mirv_streams settings add ffmpeg povforge "{s.video_options} {{QUOTE}}{{AFX_STREAM_PATH}}\\\\video.mp4{{QUOTE}}"',
        "mirv_streams record screen settings povforge",
        f"mirv_streams record fps {s.fps}",
        "mirv_streams record startMovieWav 1",
    ]
    cmds += [c.strip() for c in s.extra_setup.split(";") if c.strip()]
    return cmds


def build_job(plan: Plan, segments: list[Segment], raw_dir: Path, s: RecordSettings) -> dict:
    fwd = lambda p: str(Path(p).resolve()).replace("\\", "/")  # noqa: E731
    return {
        "player": plan.player.name,
        "steamid": plan.player.steamid,
        "demo": fwd(plan.demo_path),
        "outDir": fwd(raw_dir),
        "tickrate": plan.tickrate,
        "clips": [{"id": clip_id(sg), "start": sg.start_tick, "end": sg.end_tick} for sg in segments],
        "prerollTicks": int(round(s.preroll_seconds * plan.tickrate)),
        "specMode": s.spec_mode,
        "hideDemoUi": s.hide_demo_ui,
        "setup": setup_commands(s),
        "frameStage": 12,          # FRAME_RENDER_PASS in CS2 (HLAE docs)
        "bootFrames": 300,
        "loadTimeoutFrames": 20000,
        "seekRetryFrames": 900,
        "finishFrames": 180,
        "quitWhenDone": True,
    }


def write_director(job: dict, path: Path) -> Path:
    template = (Path(__file__).parent / "director.js").read_text(encoding="utf-8")
    path.write_text(template.replace("__POVFORGE_JOB__", json.dumps(job, ensure_ascii=False)),
                    encoding="utf-8")
    return path


def ensure_ffmpeg_ini(hlae: Path, ffmpeg: str) -> None:
    """Tell HLAE where FFmpeg is (HLAE reads ffmpeg\\ffmpeg.ini next to HLAE.exe)."""
    if (hlae.parent / "ffmpeg" / "bin" / "ffmpeg.exe").is_file():
        return
    exe = shutil.which(ffmpeg)
    if not exe:
        raise RuntimeError("FFmpeg not found on PATH; HLAE needs it to encode video.")
    ini = hlae.parent / "ffmpeg" / "ffmpeg.ini"
    ini.parent.mkdir(exist_ok=True)
    ini.write_text(f"[Ffmpeg]\nPath={Path(exe).resolve()}\n", encoding="utf-8")


def launch_command(hlae: Path, cs2: Path, s: RecordSettings) -> list[str]:
    game_args = ["-insecure", "-novid", "-condebug", "-console"]
    if s.window_mode == "fullscreen":
        game_args += ["-fullscreen"]
    else:
        game_args += ["-sw"]
    game_args += ["-width", str(s.width), "-height", str(s.height), "+exec", CFG_NAME]
    return [
        str(hlae), "-noGui", "-autoStart", "-noConfig", "-afxDisableSteamStorage",
        "-customLoader",
        "-hookDllPath", str(hlae.parent / "x64" / "AfxHookSource2.dll"),
        "-programPath", str(cs2),
        "-cmdLine", " ".join(game_args),
    ]


# --- results --------------------------------------------------------------------

_LOG = re.compile(r"\[povforge\] (START|END) (r\d+) tick=([\d.]+)")


def read_console_log(log: Path) -> dict[str, dict[str, float]]:
    """{'r03': {'START': 18376.4, 'END': 22054.0}, ...} from CS2's console.log."""
    out: dict[str, dict[str, float]] = {}
    if not log.exists():
        return out
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _LOG.search(line)
        if m:
            out.setdefault(m.group(2), {})[m.group(1)] = float(m.group(3))
    return out


def latest_take(raw_dir: Path, cid: str) -> Path | None:
    takes = sorted((raw_dir / cid).glob("take*"))
    for take in reversed(takes):
        videos = [v for v in take.rglob("video.*") if v.stat().st_size > 0]
        if videos:
            return take
    return None


def mux_take(take: Path, out: Path, ffmpeg: str) -> None:
    video = next(v for v in take.rglob("video.*") if v.stat().st_size > 0)
    audio = next(iter(take.rglob("audio.wav")), None)
    tmp = out.with_name(out.stem + ".tmp.mp4")
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-i", str(video)]
    if audio is not None and audio.stat().st_size > 44:
        cmd += ["-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "192k", "-shortest"]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v", "-map", "1:a",
                "-c:a", "aac", "-shortest"]
    cmd += ["-c:v", "copy", str(tmp)]
    subprocess.run(cmd, check=True)
    tmp.replace(out)


# --- the whole recording step ---------------------------------------------------

def _log(msg: str) -> None:
    print(msg, flush=True)


def record(plan: Plan, job_dir: Path, s: RecordSettings, ffmpeg: str = "ffmpeg") -> list[Path]:
    """Record every planned clip that isn't recorded yet; return clip paths."""
    clips_dir = job_dir / "clips"
    raw_dir = job_dir / "raw"
    clips_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    clips = [clips_dir / f"clip_{i:03d}.mp4" for i in range(len(plan.segments))]
    starts_file = job_dir / "recorded.json"
    starts = json.loads(starts_file.read_text()) if starts_file.exists() else {}

    def collect() -> None:
        for seg, out in zip(plan.segments, clips):
            take = latest_take(raw_dir, clip_id(seg))
            if take is not None and not out.exists():
                mux_take(take, out, ffmpeg)

    collect()
    todo = [seg for seg, out in zip(plan.segments, clips) if not out.exists()]
    if not todo:
        return clips

    if sys.platform != "win32":
        raise RuntimeError("Recording needs Windows with CS2 installed. "
                           "Use --placeholder to test everything else.")
    hlae, cs2 = find_hlae(s), find_cs2(s)
    procs = running_processes()
    if "cs2.exe" in procs:
        raise RuntimeError("CS2 is already running. Close it first.")
    for exe, name in ANTI_CHEAT.items():
        if exe in procs:
            _log(f"Warning: {name} is running. Close its client/anti-cheat before recording.")

    ensure_ffmpeg_ini(hlae, ffmpeg)
    director = write_director(build_job(plan, todo, raw_dir, s), job_dir / "director.js")
    csgo = csgo_dir(cs2)
    cfg = csgo / "cfg" / f"{CFG_NAME}.cfg"
    cfg.write_text(f'mirv_script_load "{str(director.resolve()).replace(chr(92), "/")}"\n',
                   encoding="utf-8")
    console_log = csgo / "console.log"
    if console_log.exists():
        console_log.unlink()

    seconds = sum(sg.duration_seconds(plan.tickrate) for sg in todo)
    limit = seconds * s.timeout_factor + 600
    _log(f"Starting CS2 through HLAE to record {len(todo)} clips (~{seconds / 60:.1f} min of video). "
         "Don't use the PC for games meanwhile; CS2 will close by itself when done.")
    try:
        # HLAE starts CS2 and normally exits right away; don't wait on it.
        subprocess.Popen(launch_command(hlae, cs2, s))
        began = time.time()
        while time.time() - began < 60 and "cs2.exe" not in running_processes():
            time.sleep(2)
        if "cs2.exe" not in running_processes():
            raise RuntimeError("CS2 did not start. Is Steam running? Is HLAE up to date?")
        done = set()
        while "cs2.exe" in running_processes():
            if time.time() - began > limit:
                subprocess.run(["taskkill", "/im", "cs2.exe", "/f"], capture_output=True)
                raise RuntimeError("Recording took far too long and was stopped. "
                                   f"Check {console_log} for [povforge] lines.")
            for cid, ev in read_console_log(console_log).items():
                if "END" in ev and cid not in done:
                    done.add(cid)
                    _log(f"Recorded {cid} ({len(done)}/{len(todo)})")
            time.sleep(5)
    finally:
        if cfg.exists():
            cfg.unlink()
        if console_log.exists():
            shutil.copy(console_log, job_dir / "cs2_console.log")

    for cid, ev in read_console_log(job_dir / "cs2_console.log").items():
        if "START" in ev:
            starts[cid] = ev["START"]
    starts_file.write_text(json.dumps(starts, indent=2))
    collect()
    missing = [clip_id(sg) for sg, out in zip(plan.segments, clips) if not out.exists()]
    if missing:
        raise RuntimeError(f"These rounds were not recorded: {', '.join(missing)}. "
                           f"See {job_dir / 'cs2_console.log'}; run the same command again to retry them.")
    return clips


def actual_starts(job_dir: Path) -> dict[str, float]:
    f = job_dir / "recorded.json"
    return json.loads(f.read_text()) if f.exists() else {}
