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
import hashlib
import math
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from . import settings_guard, tools
from .maps import parse_keyvalues
from .model import Plan, Segment

CFG_NAME = "povforge_job"
_MUX_VERSION = 2  # Preserve all video frames when the recorded WAV ends early.


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
    game_hud: str = "full"        # full = keep CS2's own HUD; killfeed = only the kill feed, povforge draws a HUD
    extra_setup: str = ""         # extra console commands, separated by ;
    timeout_factor: float = 3.0   # give up after this many times the video length (+10 min)
    player_hud: bool = False      # try cl_spec_stats 0 (on its own it doesn't replace the spectator card)

    def limit_output(self) -> None:
        from .media import bounded_size, bounded_fps
        self.width, self.height = bounded_size(self.width, self.height)
        self.fps = int(bounded_fps(self.fps))


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
        tools.hlae_exe(),                      # downloaded by `povforge setup` / the app
        Path("C:/Tools/hlae/HLAE.exe"),
        Path("C:/hlae/HLAE.exe"),
        Path(local) / "HLAE" / "HLAE.exe" if local else None,
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "HLAE" / "HLAE.exe",
    ]
    for c in candidates:
        if c is not None and c.is_file():
            return c
    raise RuntimeError(
        "HLAE not found. Run `povforge setup` to download it, or set [record] hlae_path in povforge.toml."
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
    """Lower-case names of running programs. Uses the Windows API directly, so no
    console window flashes up (the app checks this every few seconds)."""
    if sys.platform != "win32":
        return set()
    try:
        return _process_names_win32()
    except Exception:
        out = subprocess.run(["tasklist", "/fo", "csv", "/nh"], capture_output=True, text=True,
                             errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return {line.split('","')[0].strip('"').lower() for line in out.splitlines() if line}


def _process_names_win32() -> set[str]:
    import ctypes
    from ctypes import wintypes

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                    ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                    ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                    ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                    ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if snap in (None, wintypes.HANDLE(-1).value):
        raise OSError("process snapshot failed")
    names = set()
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = k32.Process32FirstW(snap, ctypes.byref(entry))
        while ok:
            names.add(entry.szExeFile.lower())
            ok = k32.Process32NextW(snap, ctypes.byref(entry))
    finally:
        k32.CloseHandle(snap)
    if not names:
        raise OSError("no processes listed")
    return names


ANTI_CHEAT = {"faceit.exe": "FACEIT", "faceitclient.exe": "FACEIT", "faceitservice.exe": "FACEIT AC",
              "5eclient.exe": "5E", "perfectworldarena.exe": "完美世界"}


# --- job files ------------------------------------------------------------------

def clip_id(seg: Segment) -> str:
    return f"r{seg.round_number:02d}"


def setup_commands(s: RecordSettings) -> list[str]:
    s.limit_output()
    cmds = [
        "sv_cheats 1",
        "demo_timescale 1",
        "demo_ui_mode 0",                       # no demo playback bar
        f"cl_draw_only_deathnotices {1 if s.game_hud == 'killfeed' else 0}",
        "cl_drawhud_force_radar -1",            # our minimap replaces the game radar
        "spec_show_xray 0",
        "mp_display_kill_assists 1",
        "cl_demo_predict 1",
        "r_show_build_info 0",
        "cl_trueview_show_status 0",
        # Experimental: hides the demo spectator card only together with a
        # Panorama mod, so it's off by default and the card stays.
        *(["cl_spec_stats 0"] if s.player_hud else []),
        "cl_spec_show_bindings 0",
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


def _validated_shots(extra_shots: list[dict] | None) -> list[dict]:
    """Keep shot names within their job folder and validate director input."""
    shots, seen = [], set()
    for item in extra_shots or []:
        cid = str(item.get("id", ""))
        if (not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", cid)
                or re.fullmatch(r"r\d+", cid, re.I)
                or re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", cid, re.I)
                or cid.lower() in seen):
            raise ValueError(f"Invalid or duplicate camera shot ID: {cid!r}")
        start, end = item.get("start"), item.get("end")
        if type(start) is not int or type(end) is not int or not 0 <= start < end:
            raise ValueError(f"Invalid camera shot range: {cid}")
        cam, steamid = item.get("cam", "pov"), str(item.get("steamid", ""))
        if cam != "pov" or not re.fullmatch(r"[0-9]{1,20}", steamid):
            raise ValueError(f"Invalid camera or player for shot: {cid}")
        shot = {"id": cid, "start": start, "end": end, "steamid": steamid, "cam": cam}
        if "focus" in item:
            focus = item["focus"]
            # Victim replays end before their associated kill.
            if type(focus) not in (int, float) or not math.isfinite(focus) or focus < 0:
                raise ValueError(f"Invalid camera focus tick: {cid}")
            shot["focus"] = focus
        if item.get("player"):
            shot["player"] = str(item["player"])
        shots.append(shot)
        seen.add(cid.lower())
    return shots


def build_job(plan: Plan, segments: list[Segment], raw_dir: Path, s: RecordSettings,
              *, extra_shots: list[dict] | None = None) -> dict:
    s.limit_output()
    fwd = lambda p: str(Path(p).resolve()).replace("\\", "/")  # noqa: E731
    return {
        "player": plan.player.name,
        "steamid": plan.player.steamid,
        "demo": fwd(plan.demo_path),
        "outDir": fwd(raw_dir),
        "tickrate": plan.tickrate,
        "clips": [{"id": clip_id(sg), "start": sg.start_tick, "end": sg.end_tick} for sg in segments]
                 + _validated_shots(extra_shots),
        "prerollTicks": int(round(s.preroll_seconds * plan.tickrate)),
        "specMode": s.spec_mode,
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
    exe = tools.find_ffmpeg(ffmpeg)
    if not exe:
        raise RuntimeError("FFmpeg not found. Run `povforge setup` to download it.")
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

_LOG = re.compile(r"\[povforge\] (START|END) ([A-Za-z][A-Za-z0-9_-]*) tick=([\d.]+)")


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
        from .media import probe

        # HLAE can stop its WAV before its video; pad silence instead of cutting video frames.
        info = probe(video, ffmpeg)
        duration = max(info.duration, info.frames / info.fps if info.fps > 0 else 0)
        samples = math.ceil(duration * 48000)
        cmd += ["-i", str(audio), "-map", "0:v", "-map", "1:a",
                "-af", f"aresample=48000,apad,atrim=end_sample={samples}",
                "-c:a", "aac", "-b:a", "192k"]
    else:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-map", "0:v", "-map", "1:a",
                "-c:a", "aac", "-shortest"]
    cmd += ["-c:v", "copy", str(tmp)]
    subprocess.run(cmd, check=True)
    tmp.replace(out)


# --- the whole recording step ---------------------------------------------------

def _log(msg: str) -> None:
    print(msg, flush=True)


def _put_settings_back(finished: bool) -> None:
    """Restore the player's CS2 settings once CS2 is closed. If recording was
    interrupted, the recording CS2 is closed at once (forced, so it doesn't
    save anything) before restoring."""
    if not finished and "cs2.exe" in running_processes():
        subprocess.run(["taskkill", "/im", "cs2.exe", "/f"], capture_output=True)
    for _ in range(60):  # CS2 writes its settings while closing
        if "cs2.exe" not in running_processes():
            break
        time.sleep(2)
    if "cs2.exe" in running_processes():
        raise RuntimeError("CS2 is still open, so your settings could not be put back yet. "
                           "The backup is kept. Close CS2, then run: povforge restore-settings")
    time.sleep(2)
    try:
        changed = settings_guard.restore()
    except Exception as e:
        raise RuntimeError(f"Could not restore your CS2 settings ({e}). The backup is kept. "
                           "Run: povforge restore-settings") from e
    if settings_guard.pending():
        raise RuntimeError("Your CS2 settings could not be fully restored. The backup is kept. "
                           "Run: povforge restore-settings")
    else:
        _log(f"Your CS2 settings are back as before ({changed} file(s) put back).")


def _check_recording_processes() -> None:
    if sys.platform != "win32":
        raise RuntimeError("Recording needs Windows with CS2 installed. "
                           "Use --placeholder to test everything else.")
    procs = running_processes()
    if "cs2.exe" in procs:
        raise RuntimeError("CS2 is already running. Close it first.")
    running = sorted({name for exe, name in ANTI_CHEAT.items() if exe in procs})
    if running:
        raise RuntimeError(
            f"{', '.join(running)} is running. Its anti-cheat stops CS2 from starting through HLAE "
            "(CS2 closes after a few seconds). Quit it completely (tray icon -> Exit), then run again.")


def record(plan: Plan, job_dir: Path, s: RecordSettings, ffmpeg: str = "ffmpeg",
           *, extra_shots: list[dict] | None = None, shots_only: bool = False) -> list[Path]:
    """Record missing clips and camera shots in one CS2 session.

    Normally returns the ordinary clip paths. With ``shots_only`` it returns
    the requested shots, in input order, and leaves ordinary clips untouched.
    """
    s.limit_output()
    shots = _validated_shots(extra_shots)
    clips_dir = job_dir / "clips"
    raw_dir = job_dir / "raw"
    clips_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    clips = [clips_dir / f"clip_{i:03d}.mp4" for i in range(len(plan.segments))]
    shot_paths = [job_dir / "shots" / f"{item['id']}.mp4" for item in shots]
    starts_file = job_dir / "recorded.json"
    starts = actual_starts(job_dir)
    manifest_file = job_dir / "shots" / "manifest.json"
    manifest = json.loads(manifest_file.read_text(encoding="utf-8")) if manifest_file.exists() else {}
    if shots:
        manifest_file.parent.mkdir(parents=True, exist_ok=True)
        demo = Path(plan.demo_path)
        stat = demo.stat()
        identity = {"demo": str(demo.resolve()), "size": stat.st_size, "mtime": stat.st_mtime_ns,
                    "tickrate": plan.tickrate, "settings": asdict(s), "mux_version": _MUX_VERSION,
                    "director": hashlib.sha256(Path(__file__).with_name("director.js").read_bytes()).hexdigest()}
        for item, out in zip(shots, shot_paths):
            cid = item["id"]
            signature = hashlib.sha256(json.dumps([identity, item], sort_keys=True).encode("utf-8")).hexdigest()
            cached = manifest.get(cid, {})
            if (cached.get("signature") != signature or not cached.get("complete")
                    or not out.exists() or out.stat().st_size == 0 or cid not in starts):
                out.unlink(missing_ok=True)
                # IDs are validated; also resolve the final target before recursive removal.
                raw_shot = (raw_dir / cid).resolve()
                if raw_shot.parent != raw_dir.resolve():
                    raise ValueError("Camera raw path escapes the job folder")
                if raw_shot.exists():
                    shutil.rmtree(raw_shot)
                starts.pop(cid, None)
                manifest[cid] = {"signature": signature, "complete": False}
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def collect() -> None:
        saved_console = job_dir / "cs2_console.log"
        console_text = saved_console.read_text(encoding="utf-8", errors="replace") if saved_console.exists() else ""
        failed = set(re.findall(
            r"\[povforge\] END ([A-Za-z][A-Za-z0-9_-]*) tick=[\d.]+ why=(?:camera_error|error)\b",
            console_text,
        ))
        for cid in failed:
            # The next session replaces the console log. Remove failed material now
            # so a later empty retry cannot make an old partial take appear valid.
            failed_raw = (raw_dir / cid).resolve()
            if failed_raw.parent != raw_dir.resolve():
                raise ValueError("Failed recording path escapes the job folder")
            if failed_raw.exists():
                shutil.rmtree(failed_raw)
            starts.pop(cid, None)
        if failed:
            starts_file.write_text(json.dumps(starts, indent=2), encoding="utf-8")
        for seg, out in ([] if shots_only else zip(plan.segments, clips)):
            if clip_id(seg) in failed:
                continue  # never turn a failed camera take into a resumable ordinary clip
            take = latest_take(raw_dir, clip_id(seg))
            if take is not None and not out.exists():
                mux_take(take, out, ffmpeg)
            if out.exists():
                # the clip holds the same picture: the raw take is no longer needed
                shutil.rmtree(raw_dir / clip_id(seg), ignore_errors=True)

    collect()
    todo = [] if shots_only else [seg for seg, out in zip(plan.segments, clips) if not out.exists()]
    shot_todo = [item for item, out in zip(shots, shot_paths) if not out.exists()]
    result = shot_paths if shots_only else clips
    if not todo and not shot_todo:
        return result

    _check_recording_processes()
    hlae, cs2 = find_hlae(s), find_cs2(s)

    csgo = csgo_dir(cs2)
    cfg = csgo / "cfg" / f"{CFG_NAME}.cfg"
    console_log = csgo / "console.log"
    saved_log = job_dir / "cs2_console.log"
    # Back up the player's CS2 settings before anything else touches them.
    n = settings_guard.backup(_steam_dir(), csgo_dir(cs2))
    _log(f"Backed up your CS2 settings ({n} files); they are put back after recording.")
    finished = False
    log_reset = False
    cfg_captured = False
    original_cfg = None
    try:
        # backup() may first restore a previous interrupted session, including this cfg.
        original_cfg = cfg.read_bytes() if cfg.exists() else None
        cfg_captured = True
        ensure_ffmpeg_ini(hlae, ffmpeg)
        director = write_director(build_job(plan, todo, raw_dir, s, extra_shots=shot_todo),
                                  job_dir / "director.js")
        cfg.write_text(f'mirv_script_load "{str(director.resolve()).replace(chr(92), "/")}"\n',
                       encoding="utf-8")
        console_log.unlink(missing_ok=True)
        saved_log.unlink(missing_ok=True)
        log_reset = True
        seconds = (sum(sg.duration_seconds(plan.tickrate) for sg in todo)
                   + sum((item["end"] - item["start"]) / plan.tickrate for item in shot_todo))
        count = len(todo) + len(shot_todo)
        limit = seconds * s.timeout_factor + 600
        _log(f"Starting CS2 through HLAE to record {count} clips (~{seconds / 60:.1f} min of video). "
             "Don't use the PC for games meanwhile; CS2 will close by itself when done.")
        # HLAE starts CS2 and normally exits right away; don't wait on it.
        subprocess.Popen(launch_command(hlae, cs2, s),
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        began = time.time()
        while time.time() - began < 60 and "cs2.exe" not in running_processes():
            time.sleep(2)
        if "cs2.exe" not in running_processes():
            raise RuntimeError("CS2 did not start. Is Steam running? Is HLAE up to date?")
        started = time.time()
        done = set()
        while "cs2.exe" in running_processes():
            if time.time() - began > limit:
                subprocess.run(["taskkill", "/im", "cs2.exe", "/f"], capture_output=True)
                raise RuntimeError("Recording took far too long and was stopped. "
                                   f"Check {console_log} for [povforge] lines.")
            events = read_console_log(console_log)
            for cid, ev in events.items():
                if "END" in ev and cid not in done:
                    done.add(cid)
                    _log(f"Recorded {cid} ({len(done)}/{count})")
            time.sleep(5)
        finished = True
        if not done and not read_console_log(console_log) and time.time() - started < 90:
            raise RuntimeError(
                "CS2 closed right after starting, before recording began. Usual causes: an anti-cheat "
                "client (FACEIT, 5E, Perfect World) still running in the background, or HLAE needing "
                "an update after a CS2 patch.")
    finally:
        try:
            if cfg_captured:
                if original_cfg is None:
                    cfg.unlink(missing_ok=True)
                else:
                    cfg.write_bytes(original_cfg)
        finally:
            try:
                _put_settings_back(finished)
            finally:
                if log_reset and console_log.exists():
                    shutil.copy(console_log, saved_log)
                    for cid, ev in read_console_log(saved_log).items():
                        if "START" in ev:
                            starts[cid] = ev["START"]
                    starts_file.write_text(json.dumps(starts, indent=2), encoding="utf-8")

    collect()
    log_text = saved_log.read_text(encoding="utf-8", errors="replace") if saved_log.exists() else ""
    for item, out in zip(shots, shot_paths):
        cid = item["id"]
        if out.exists():
            continue
        # A failed view or an interrupted demo must not be cached as a successful shot.
        completed = re.search(rf"\[povforge\] END {re.escape(cid)} tick=[\d.]+ why=end_tick\b", log_text)
        take = latest_take(raw_dir, cid)
        if completed and cid in starts and take is not None:
            mux_take(take, out, ffmpeg)
            manifest[cid]["complete"] = True
    if shots:
        manifest_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    missing = ([] if shots_only else [clip_id(sg) for sg, out in zip(plan.segments, clips) if not out.exists()])
    missing += [item["id"] for item, out in zip(shots, shot_paths) if not out.exists()]
    if missing:
        raise RuntimeError(f"These clips were not recorded: {', '.join(missing)}. "
                           f"See {job_dir / 'cs2_console.log'}; run the same command again to retry them.")
    return result


def actual_starts(job_dir: Path) -> dict[str, float]:
    f = job_dir / "recorded.json"
    return json.loads(f.read_text()) if f.exists() else {}
