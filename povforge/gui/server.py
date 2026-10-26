"""PovForge app: a small local web server plus a page that drives the pipeline.

Run with ``povforge gui`` (or the packaged PovForge.exe). It listens on
127.0.0.1 only and opens a native WebView2 window on Windows (with a browser
fallback). Recording runs ``povforge run`` as a child process, so
the app shows the same steps and messages as the command line.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .. import __version__

STATIC = Path(__file__).parent / "static"
DEMO_SUFFIXES = (".dem", ".dem.zst", ".dem.gz", ".dem.bz2")
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".js": "text/javascript; charset=utf-8", ".svg": "image/svg+xml",
                 ".woff2": "font/woff2", ".png": "image/png", ".json": "application/json"}


# --- settings for the app ------------------------------------------------------

def app_dir() -> Path:
    base = os.environ.get("POVFORGE_STATE") or os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "povforge"


def default_output() -> Path:
    videos = Path.home() / "Videos"
    return (videos if videos.is_dir() else Path.home()) / "PovForge"


ACCENTS = ("blue", "purple", "pink", "red", "orange", "yellow", "green", "graphite")
FONTS = ("system", "segoe", "yahei", "simsun", "arial")


def update_appearance(prefs: dict, values: dict) -> None:
    for key, allowed in (("appearance", ("auto", "light", "dark")), ("accent", ACCENTS), ("font", FONTS)):
        if values.get(key) in allowed:
            prefs[key] = values[key]
    radius = values.get("popup_radius")
    if type(radius) is int and 0 <= radius <= 28:
        prefs["popup_radius"] = radius


def load_prefs() -> dict:
    f = app_dir() / "app.json"
    prefs = {"output": str(default_output()), "demo_folders": [str(Path.home() / "Downloads")],
             "intro": True, "minimap": True, "keyboard": True, "show_enemies": False, "lang": "",
             "upload": True, "appearance": "auto", "accent": "blue", "font": "system", "popup_radius": 14,
             "by_player": True,          # finished videos go into a folder per player
             "record_res": "1080",       # fixed app output size
             "record_fps": 60,
             "player_folders": {},       # steamid -> {"folder": name on disk, "name": in-game name}
             "folders_set": False}       # first run: the user picks where demos are and where videos go
    if f.exists():
        try:
            saved = json.loads(f.read_text(encoding="utf-8"))
            saved.setdefault("folders_set", True)    # set up before this existed: keep their folders
            prefs.update(saved)
        except Exception:
            pass
    prefs.pop("upload_4k", None)
    prefs["record_res"] = "1080"
    prefs["record_fps"] = record_fps(prefs)
    if prefs.get("font") not in FONTS:
        prefs["font"] = "system"
    if type(prefs.get("popup_radius")) is not int or not 0 <= prefs["popup_radius"] <= 28:
        prefs["popup_radius"] = 14
    return prefs


def save_prefs(prefs: dict) -> None:
    app_dir().mkdir(parents=True, exist_ok=True)
    # Write beside the destination so a failed save leaves the previous file intact.
    import tempfile

    fd, name = tempfile.mkstemp(dir=app_dir(), prefix="app-", suffix=".tmp")
    os.close(fd)
    temp = Path(name)
    try:
        temp.write_text(json.dumps(prefs, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(app_dir() / "app.json")
    finally:
        temp.unlink(missing_ok=True)


def _toml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)  # a JSON string is a valid TOML basic string


def write_job_config(prefs: dict, videos: Path | None = None) -> Path:
    """povforge.toml for one run, from the app's switches; ``videos`` = folder for the finished video."""
    lines = ["[output]", f"dir = {_toml_str(prefs['output'])}"]
    if videos is not None:
        videos.mkdir(parents=True, exist_ok=True)
        lines.append(f"videos = {_toml_str(str(videos))}")
    lines += ["",
             "[overlay]", f"minimap = {str(bool(prefs['minimap'])).lower()}",
             f"keyboard = {str(bool(prefs['keyboard'])).lower()}",
             f"show_enemies = {str(bool(prefs['show_enemies'])).lower()}", "",
             "[intro]", f"enabled = {str(bool(prefs['intro'])).lower()}", "",
             "[highlights]", "enabled = false", "",      # highlights are made as a reel now
             "[upload]", f"enabled = {str(bool(prefs.get('upload', True))).lower()}"]
    w, h = record_size(prefs)
    lines += ["", "[record]", f"width = {w}", f"height = {h}", f"fps = {record_fps(prefs)}",
              'video_options = "-c:v libx264 -pix_fmt yuv420p -preset veryfast -crf 12"',
              "", "[compose]", "crf = 15", 'preset = "medium"', ""]
    f = app_dir() / "last-run.toml"
    app_dir().mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(lines), encoding="utf-8")
    return f


# --- recording size ----------------------------------------------------------------

SIZES = {"1080": (1920, 1080)}
FRAME_RATES = (24, 30, 60, 120, 144, 240)


def record_fps(prefs: dict) -> int:
    value = prefs.get("record_fps", 60)
    return value if type(value) is int and value in FRAME_RATES else 60


def screen_size() -> tuple[int, int] | None:
    """The main screen's resolution in real pixels (Windows), or None if unknown."""
    if sys.platform != "win32":
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class DEVMODE(ctypes.Structure):
            _fields_ = [("dmDeviceName", wintypes.WCHAR * 32), ("dmSpecVersion", wintypes.WORD),
                        ("dmDriverVersion", wintypes.WORD), ("dmSize", wintypes.WORD),
                        ("dmDriverExtra", wintypes.WORD), ("dmFields", wintypes.DWORD),
                        ("dmPositionX", wintypes.LONG), ("dmPositionY", wintypes.LONG),
                        ("dmDisplayOrientation", wintypes.DWORD), ("dmDisplayFixedOutput", wintypes.DWORD),
                        ("dmColor", ctypes.c_short), ("dmDuplex", ctypes.c_short), ("dmYResolution", ctypes.c_short),
                        ("dmTTOption", ctypes.c_short), ("dmCollate", ctypes.c_short),
                        ("dmFormName", wintypes.WCHAR * 32), ("dmLogPixels", wintypes.WORD),
                        ("dmBitsPerPel", wintypes.DWORD), ("dmPelsWidth", wintypes.DWORD),
                        ("dmPelsHeight", wintypes.DWORD), ("dmDisplayFlags", wintypes.DWORD),
                        ("dmDisplayFrequency", wintypes.DWORD)]
        dm = DEVMODE()
        dm.dmSize = ctypes.sizeof(DEVMODE)
        if ctypes.windll.user32.EnumDisplaySettingsW(None, -1, ctypes.byref(dm)):   # ENUM_CURRENT_SETTINGS
            return int(dm.dmPelsWidth), int(dm.dmPelsHeight)
    except Exception:
        pass
    return None


def fitting_sizes(screen: tuple[int, int] | None) -> list[str]:
    """The 16:9 recording sizes that fit on the screen (CS2 records in a window on it)."""
    if screen is None:
        return list(SIZES)
    sw, sh = screen
    fit = [k for k, (w, h) in SIZES.items() if w <= sw and h <= sh]
    return fit


def record_size(prefs: dict, screen: tuple[int, int] | None = None) -> tuple[int, int]:
    """The app always outputs 1080p, including after loading older preferences."""
    return SIZES["1080"]



# --- a folder per player ----------------------------------------------------------

MULTI_FOLDER = {"zh": "多人集锦", "en": "Multi-player reels"}
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}
VIDEO_EXT = (".mp4", ".mkv", ".mov")


def folder_name(s: str) -> str:
    """A name that works as a Windows folder."""
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(s)).strip(" .")[:60].strip(" .")
    if not s or s.lower() in _RESERVED or s == WORK_DIR_NAME:
        s = (s or "player") + "_"
    return s


def player_folder(prefs: dict, steamid: str, name: str = "") -> str:
    """The folder for a player's videos: their in-game name the first time, then kept
    (a new nickname doesn't split their videos; the user can rename the folder)."""
    folders = prefs.setdefault("player_folders", {})
    entry = folders.get(steamid)
    if entry is None:
        base = folder_name(name or steamid)
        taken = {e["folder"].lower() for e in folders.values()}
        folder, n = base, 2
        while folder.lower() in taken or folder in MULTI_FOLDER.values():
            folder, n = f"{base} ({n})", n + 1
        entry = folders[steamid] = {"folder": folder, "name": name or steamid}
    elif name:
        entry["name"] = name
    return entry["folder"]


def videos_folder(prefs: dict, item: dict) -> Path | None:
    """Where a queue item's video goes: the player's folder, or the multi-player folder
    for a reel of several players (None = the output folder itself)."""
    if not prefs.get("by_player", True):
        return None
    base = Path(prefs["output"])
    if item.get("kind") == "reel":
        ids = list(dict.fromkeys(str(i["steamid"]) for i in item.get("reel", [])))
        if len(ids) != 1:
            return base / MULTI_FOLDER.get(prefs.get("lang") or "zh", MULTI_FOLDER["zh"])
        name = next((i.get("name") for i in item["reel"] if i.get("name")), "")
        sid = ids[0]
    else:
        sid, name = str(item.get("steamid", "")), item.get("name", "")
    folder = player_folder(prefs, sid, name)
    custom = prefs["player_folders"][sid].get("path")
    return Path(custom) if custom else base / folder


def _move_into(src: Path, folder: Path) -> Path:
    """Move a file or folder into ``folder`` without overwriting anything."""
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / src.name
    if dest.exists():
        if src.is_dir() and dest.is_dir():
            for child in list(src.iterdir()):
                _move_into(child, dest)
            try:
                src.rmdir()
            except OSError:
                pass
            return dest
        stem, suffix, n = src.stem, src.suffix, 2
        while dest.exists():
            dest, n = folder / f"{stem} ({n}){suffix}", n + 1
    src.replace(dest)
    return dest


def _move_video(video: Path, folder: Path) -> None:
    """A video and the cover and description that share its name."""
    extras = [video.with_suffix(x) for x in (".jpg", ".txt") if video.with_suffix(x).exists()]
    dest = _move_into(video, folder)
    for e in extras:
        target = dest.with_suffix(e.suffix)
        if not target.exists():
            e.replace(target)


def rename_player_folder(prefs: dict, steamid: str, new: str) -> None:
    """Rename a player's folder, on disk too (merging into a folder of that name if there is one)."""
    folders = prefs.get("player_folders", {})
    entry = folders.get(steamid)
    if entry is None:
        raise ValueError("unknown player")
    new = folder_name(new)
    if new == entry["folder"]:
        return
    if any(e["folder"].lower() == new.lower() for sid, e in folders.items() if sid != steamid):
        raise ValueError("taken")
    base = Path(prefs["output"])
    src, dst = base / entry["folder"], base / new
    if src.is_dir():
        if dst.exists() and src.resolve() != dst.resolve():
            for child in list(src.iterdir()):
                _move_into(child, dst)
            src.rmdir()
        else:
            src.replace(dst)              # also a change of upper/lower case only
    entry["folder"] = new


def _video_owners(base: Path) -> dict[str, tuple[str, str]]:
    """Finished video name -> (steamid, player name), from the jobs that made them."""
    owners: dict[str, tuple[str, str]] = {}
    for root in (base / WORK_DIR_NAME, base):
        if not root.is_dir():
            continue
        for rec in root.glob("*/published.json"):
            try:
                video = json.loads(rec.read_text(encoding="utf-8")).get("video", "")
                player = json.loads((rec.parent / "plan.json").read_text(encoding="utf-8"))["player"]
                if video:
                    owners[video] = (str(player["steamid"]), str(player["name"]))
            except Exception:
                continue
    return owners


def _known_players(base: Path) -> dict[str, str]:
    """steamid -> name of every player with a job in the work folder."""
    out: dict[str, str] = {}
    for root in (base / WORK_DIR_NAME, base):
        if root.is_dir():
            for f in root.glob("*/plan.json"):
                try:
                    p = json.loads(f.read_text(encoding="utf-8"))["player"]
                    out[str(p["steamid"])] = str(p["name"])
                except Exception:
                    continue
    return out


def organize_existing(prefs: dict) -> str:
    """Once: sort the videos already in the output folder into player folders.

    If the output folder already is one player's folder (say .../Pro POV/donk with
    only donk666's videos), it becomes that player's folder and its parent the new
    output folder, so nothing in it has to move but the work files. Returns a note."""
    prefs["organized"] = True
    base = Path(prefs["output"])
    if not base.is_dir():
        return ""
    videos = [v for v in base.iterdir() if v.is_file() and v.suffix.lower() in VIDEO_EXT]
    owners = _video_owners(base)
    players = _known_players(base)
    whose: dict[Path, tuple[str, str]] = {}
    for v in videos:
        if v.name in owners:
            whose[v] = owners[v.name]
        else:                                          # a reel: named after its player by default
            for sid, name in sorted(players.items(), key=lambda x: -len(x[1])):
                if name and v.stem.lower().startswith(name.lower()):
                    whose[v] = (sid, name)
                    break
    ids = {sid for sid, _ in whose.values()}
    if len(ids) == 1 and len(whose) == len(videos):
        sid, name = next(iter(whose.values()))
        here = base.name.lower()
        if here and (here in name.lower() or name.lower() in here) and base.parent != base:
            parent = base.parent
            if (base / WORK_DIR_NAME).is_dir():
                _move_into(base / WORK_DIR_NAME, parent)
            prefs.setdefault("player_folders", {})[sid] = {"folder": base.name, "name": name}
            prefs["output"] = str(parent)
            print(f"Sorted by player: {base} is now {name}'s folder in {parent}", flush=True)
            return str(parent)
    moved = 0
    for v, (sid, name) in whose.items():
        _move_video(v, base / player_folder(prefs, sid, name))
        moved += 1
    if moved:
        print(f"Sorted by player: {moved} video(s) moved into player folders in {base}", flush=True)
    return str(base) if moved else ""


# --- work files ------------------------------------------------------------------

WORK_DIR_NAME = "工作文件"     # same as Config.work_dir_name


def work_dir(prefs: dict) -> Path:
    return Path(prefs["output"]) / WORK_DIR_NAME


def folder_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def clean_work(prefs: dict) -> int:
    """Delete the work folder (recordings kept for retries). Returns bytes freed."""
    d = work_dir(prefs)
    if not d.is_dir() or d.name != WORK_DIR_NAME:
        return 0
    size = folder_size(d)
    shutil.rmtree(d, ignore_errors=True)
    return size


# --- demos ---------------------------------------------------------------------

def is_demo(p: Path) -> bool:
    return p.is_file() and p.name.lower().endswith(DEMO_SUFFIXES)


def find_demos(folders: list[str], limit: int = 40) -> list[dict]:
    seen, out = set(), []
    for folder in folders:
        d = Path(folder).expanduser()
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if not is_demo(p):
                continue
            # a .dem unpacked next to its .dem.zst is the same demo
            if p.suffix.lower() == ".dem" and any(p.with_name(p.name + s).exists() for s in (".zst", ".gz", ".bz2")):
                continue
            key = str(p.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            st = p.stat()
            out.append({"path": str(p), "name": p.name, "size": st.st_size, "mtime": st.st_mtime,
                        "faceit": bool(re.search(r"1-[0-9a-f]{8}-", p.name, re.I))})
    out.sort(key=lambda d: -d["mtime"])
    known = _known_demos()
    for d in out:
        d["cached"] = _inspection_file(_inspection_key(Path(d["path"]))).is_file()
        k = known.get(d["path"])
        if k:
            d["map"], d["score"] = k.get("map", ""), k.get("score", "")
    return out[:limit]


def _known_demos() -> dict:
    f = app_dir() / "demos.json"
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _remember_demo(path: str, map_pretty: str, score: str) -> None:
    known = _known_demos()
    known[path] = {"map": map_pretty, "score": score}
    app_dir().mkdir(parents=True, exist_ok=True)
    (app_dir() / "demos.json").write_text(json.dumps(known, ensure_ascii=False), encoding="utf-8")


_inspect_cache: dict[str, dict] = {}


def inspect_demo(path: str, work_dir: Path) -> dict:
    from ..demo import load_demo, load_scoreboard, prepare_demo, event_round_end
    from ..faceit import match_id
    from ..intro import pretty_map

    src = Path(path)
    key = f"{src.resolve()}|{src.stat().st_mtime}"
    if key in _inspect_cache:
        return _inspect_cache[key]
    dem = prepare_demo(src, work_dir / "demos")
    d = load_demo(dem)
    try:
        teams = load_scoreboard(dem, len(d.rounds))
    except Exception:
        teams = []
    # per player and round: kills, and whether they died
    ends = [event_round_end(d, r) for r in d.rounds]
    starts = [r.freeze_end_tick for r in d.rounds]

    def round_of(tick: int) -> int | None:
        for i, (a, b) in enumerate(zip(starts, ends)):
            if a <= tick < b:
                return i
        return None

    n = len(d.rounds)
    kills = {p.steamid: [0] * n for p in d.players}
    event_kills = {p.steamid: [0] * n for p in d.players}
    from ..reel_events import first_person_kills
    for i, (a, b) in enumerate(zip(starts, ends)):
        for death in first_person_kills([death for death in d.deaths if a <= death.tick < b]):
            if death.attacker_steamid in event_kills:
                event_kills[death.attacker_steamid][i] += 1
    died = {p.steamid: [False] * n for p in d.players}
    for death in d.deaths:
        i = round_of(death.tick)
        if i is None:
            continue
        if death.victim_steamid in died:
            died[death.victim_steamid][i] = True
        a = death.attacker_steamid
        if a in kills and a != death.victim_steamid:
            kills[a][i] += 1
    # kills, headshots and won clutches per round (for the highlight reel)
    table = {}
    sides = {}
    try:
        from ..demo import round_sides
        from ..highlights import round_table
        sides = round_sides(dem, d.rounds)
        table = round_table(d.rounds, d.deaths, d.winners, sides)
    except Exception:
        pass

    def per_round(sid: str) -> dict:
        rows = table.get(sid)
        if not rows:
            return {"rounds_k": kills.get(sid, []), "rounds_event_k": event_kills.get(sid, []), "rounds_died": died.get(sid, []),
                    "rounds_hs": [0] * n, "rounds_clutch": [0] * n, "rounds_won": [None] * n}
        return {"rounds_k": [r.kills for r in rows], "rounds_event_k": event_kills.get(sid, []), "rounds_died": died.get(sid, []),
                "rounds_hs": [r.headshots for r in rows], "rounds_clutch": [r.clutch for r in rows],
                "rounds_won": [r.won for r in rows]}

    known = {p.steamid for t in teams for p in t.players}
    loose = [p for p in d.players if p.steamid not in known]
    out_teams = [{"name": t.name, "score": t.score,
                  "players": [{"steamid": p.steamid, "name": p.name, "k": p.kills, "d": p.deaths,
                               "a": p.assists, "adr": round(p.adr), "hs": round(p.hs_pct), **per_round(p.steamid)}
                              for p in t.players]} for t in teams]
    if loose:
        out_teams.append({"name": "", "score": None,
                          "players": [{"steamid": p.steamid, "name": p.name, "k": None, "d": None, "a": None,
                                       "adr": None, "hs": None, **per_round(p.steamid)} for p in loose]})
    from ..reel_events import duel_events
    info = {"path": str(src), "name": src.name, "map": d.map_name, "map_pretty": pretty_map(d.map_name),
            "duels": duel_events(d, sides),
            "rounds": n, "minutes": round(d.last_tick / d.tickrate / 60, 1), "faceit_match": match_id(src.name),
            "date": time.strftime("%Y-%m-%d %H:%M", time.localtime(src.stat().st_mtime)), "teams": out_teams}
    from ..recording_details import build
    info['recording_details'] = build(d)
    _inspect_cache[key] = info
    score = f"{out_teams[0]['score']}:{out_teams[1]['score']}" if len(out_teams) >= 2 and out_teams[1]["score"] is not None else ""
    _remember_demo(str(src), info["map_pretty"], score)
    return info


INSPECT_VERSION = 4       # v4 excludes posthumous kills from event counts and duels
_inspect_locks = [threading.Lock() for _ in range(32)]


def _inspection_key(src: Path) -> str:
    st = src.stat()
    # Keep the existing disk key so an app update does not discard valid results.
    return f"{src.resolve()}|{st.st_mtime}|{st.st_size}|v{INSPECT_VERSION}"


def _inspection_file(key: str) -> Path:
    import hashlib
    return app_dir() / "demo-info" / (hashlib.sha1(key.encode("utf-8")).hexdigest() + ".json")


def inspect_isolated(path: str, work_dir: Path, details: bool = False) -> dict:
    """inspect_demo in a child process: reading a big demo then can't stall the
    app, and a crash in the demo parser can't take the app down with it."""
    # Concurrent clicks/windows share one parse. Bounded locks avoid accumulating
    # one lock per demo; distinct stripes can still parse independently.
    with _inspect_locks[hash(_inspection_key(Path(path))) % len(_inspect_locks)]:
        return _inspect_saved(path, work_dir, details)


def _inspect_saved(path: str, work_dir: Path, details: bool = False) -> dict:
    src = Path(path)
    key = _inspection_key(src)
    def usable(info):
        return not details or info.get('recording_details', {}).get('version') == 1
    if key in _inspect_cache and usable(_inspect_cache[key]):
        return _inspect_cache[key]
    saved = _inspection_file(key)
    if saved.exists():                        # read before, even in an earlier session
        try:
            info = json.loads(saved.read_text(encoding="utf-8"))
            if not isinstance(info, dict):
                raise ValueError("Invalid demo cache")
            if usable(info):
                _inspect_cache[key] = info
                return info
        except Exception:
            pass
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run(cli_command("inspect", str(src), "--json", "--work", str(work_dir)),
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=900, env=env, creationflags=flags)
    out = [l for l in r.stdout.splitlines() if l.startswith("{")]
    if r.returncode != 0 or not out:
        tail = (r.stderr or r.stdout).strip().splitlines()
        raise RuntimeError(tail[-1] if tail else f"Reading the demo failed (exit code {r.returncode}).")
    info = json.loads(out[-1])
    if _inspection_key(src) != key:
        raise RuntimeError("The demo changed while it was being read. Please open it again.")
    _inspect_cache[key] = info
    temporary = saved.with_suffix("." + secrets.token_hex(8) + ".tmp")
    try:
        saved.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        temporary.replace(saved)
    except OSError:
        pass
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass  # Saving an optional cache must not prevent opening the demo.
    return info


def analyze_isolated(path: str) -> dict:
    """style.analyze in a child process (it can take a while on a long video).
    ``path`` may also be a link: the child downloads a small copy first."""
    from ..style import is_link
    if not is_link(path) and not Path(path).is_file():
        raise ValueError("The video was not found.")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    r = subprocess.run(cli_command("analyze-style", str(path).strip(), "--json"), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=1800, env=env, creationflags=flags)
    out = [l for l in r.stdout.splitlines() if l.startswith("{")]
    if r.returncode != 0 or not out:
        tail = (r.stderr or r.stdout).strip().splitlines()
        raise RuntimeError(tail[-1] if tail else f"Reading the video failed (exit code {r.returncode}).")
    return json.loads(out[-1])


def stop_reference_process(proc) -> None:
    if proc.poll() is not None:
        return
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/pid", str(proc.pid), "/t", "/f"],
                       capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
    else:
        import signal
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if proc.poll() is None:
        proc.kill()
    proc.wait(timeout=15)


def reference_isolated(*args: str, owner=None) -> dict:
    """Bounded reference task; timeout also stops its own download/encoder children."""
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    launch = owner.launch if owner is not None else subprocess.Popen
    proc = launch(cli_command("reference", *args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                  text=True, encoding="utf-8", errors="replace",
                  env=dict(os.environ, PYTHONIOENCODING="utf-8"), creationflags=flags,
                  start_new_session=sys.platform != "win32")
    try:
        try:
            stdout, stderr = proc.communicate(timeout=900)
        except subprocess.TimeoutExpired:
            stop_reference_process(proc)
            proc.communicate()
            raise RuntimeError("Reference preparation timed out. Try a shorter local video.") from None
    finally:
        if owner is not None:
            with owner.process_lock:
                owner.processes.discard(proc)
    lines = [line for line in stdout.splitlines() if line.startswith("{")]
    if proc.returncode or not lines:
        detail = (stderr or stdout).strip().splitlines()
        raise RuntimeError(detail[-1] if detail else "Reference processing failed.")
    return json.loads(lines[-1])


class ReferenceLibrary:
    """Only opaque session IDs can expose selected preview media to the browser."""
    def __init__(self):
        import tempfile
        self.temp = tempfile.TemporaryDirectory(prefix="povforge-references-", ignore_cleanup_errors=True)
        self.items: dict[str, dict] = {}
        self.lock = threading.Lock()
        self.process_lock = threading.Lock()
        self.processes = set()
        self.closed = False

    def launch(self, *args, **kwargs):
        with self.process_lock:
            if self.closed:
                raise RuntimeError("Reference session is closed.")
            proc = subprocess.Popen(*args, **kwargs)
            self.processes.add(proc)
            return proc

    def prepare(self, source: str) -> dict:
        import uuid
        if not self.lock.acquire(blocking=False):
            raise ValueError("A reference is already being prepared.")
        folder = Path(self.temp.name) / uuid.uuid4().hex
        try:
            if self.closed:
                raise RuntimeError("Reference session is closed.")
            result = reference_isolated("prepare", source, "--folder", str(folder), owner=self)
            key = folder.name
            with self.process_lock:
                if self.closed:
                    raise RuntimeError("Reference session is closed.")
                self.items[key] = result
            # The window uses one current source; retain a few recent sources for in-flight requests.
            while len(self.items) > 4:
                old = next(iter(self.items))
                self.items.pop(old)
                shutil.rmtree(Path(self.temp.name) / old, ignore_errors=True)
            return {"id": key, "title": result["title"], "duration": result["duration"],
                    "preview": f"/api/style/video?id={key}"}
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        finally:
            self.lock.release()

    def get(self, key: str) -> dict:
        if self.closed or key not in self.items:
            raise ValueError("Reference expired. Import it again.")
        return self.items[key]

    def close(self) -> None:
        with self.process_lock:
            self.closed = True
            processes = list(self.processes)
        for proc in processes:
            stop_reference_process(proc)
        self.items.clear()
        self.temp.cleanup()


# --- recording job -----------------------------------------------------------------

def cli_command(*args: str) -> list[str]:
    if getattr(sys, "frozen", False):          # packaged app: povforge-cli.exe sits next to PovForge.exe
        cli = Path(sys.executable).with_name("povforge-cli.exe")
        return [str(cli if cli.exists() else sys.executable), *args]
    return [sys.executable, "-m", "povforge.cli", *args]


def rounds_spec(rounds: list[int]) -> str:
    """[1,2,3,7,9,10] -> '1-3,7,9-10'."""
    rs = sorted(set(rounds))
    parts, i = [], 0
    while i < len(rs):
        j = i
        while j + 1 < len(rs) and rs[j + 1] == rs[j] + 1:
            j += 1
        parts.append(str(rs[i]) if i == j else f"{rs[i]}-{rs[j]}")
        i = j + 1
    return ",".join(parts)


class Job:
    """One `povforge run` child process and what it has reported so far."""

    STAGES = ["read", "record", "overlays", "intro", "compose", "extras", "cut", "done"]

    def __init__(self):
        self.lock = threading.Lock()
        self.on_finish = None        # called (outside the lock) when the child process ends
        self.reset()

    def reset(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.cancelling = False
        self._finish_notified = False
        self.state = "idle"          # idle | running | done | error | cancelled
        self.stage = ""
        self.lines: list[str] = []
        self.recorded: list[int] = []
        self.planned: list[int] = []
        self.step = (0, 0)           # (done, total) within the current stage
        self.result = ""
        self.highlights = ""
        self.cover = ""
        self.description = ""
        self.title = ""
        self.error = ""
        self.player = ""
        self.demo = ""
        self.item = 0                # queue item being recorded
        self.kind = "match"          # match | reel
        self.source = (0, 0)         # reel: which demo of how many
        self.started = 0.0

    @property
    def busy(self) -> bool:
        return (self.state == "running" or self.cancelling
                or (self.proc is not None and self.proc.poll() is None))

    def restore_settings(self) -> None:
        """Serialize manual recovery with startup; never restore a live game's files."""
        from .. import hlae, settings_guard
        with self.lock:
            if self.busy or "cs2.exe" in hlae.running_processes():
                raise RuntimeError("Close CS2 and wait for recording cleanup before restoring settings.")
            settings_guard.restore()

    def snapshot(self) -> dict:
        with self.lock:
            return {"state": self.state, "stage": self.stage, "lines": self.lines[-200:],
                    "recorded": self.recorded, "planned": self.planned, "step": list(self.step),
                    "result": self.result, "highlights": self.highlights, "cover": self.cover,
                    "description": self.description, "title": self.title, "error": self.error,
                    "player": self.player, "demo": self.demo, "item": self.item, "kind": self.kind,
                    "source": list(self.source),
                    "elapsed": time.time() - self.started if self.started else 0}

    def start(self, item: dict, prefs: dict) -> None:
        """Start a queue item: a whole-match recording or a highlight reel."""
        kind = item.get("kind", "match")
        with self.lock:
            if self.busy:
                raise RuntimeError("A recording is already running.")
            self.reset()
            self.state, self.stage, self.started = "running", "read", time.time()
            self.player, self.demo, self.item, self.kind = item["name"], item.get("path", ""), item.get("id", 0), kind
            self.planned = sorted(item.get("rounds") or [])
        try:
            self._launch(item, prefs, kind)
        except Exception as e:
            with self.lock:
                self.state, self.error = "error", str(e)
            raise

    def _launch(self, item: dict, prefs: dict, kind: str) -> None:
        videos = videos_folder(prefs, item)
        live = item.get('_live_prefs', prefs)
        if live is not prefs:
            for sid, entry in prefs.get('player_folders', {}).items():
                live.setdefault('player_folders', {}).setdefault(sid, entry)
        save_prefs(live)                          # never replace current UI preferences with an old task
        cfg = write_job_config(prefs, videos)
        if kind == "reel":
            spec = app_dir() / "reels" / f"reel-{item.get('id', 0)}.json"
            spec.parent.mkdir(parents=True, exist_ok=True)
            spec.write_text(json.dumps({"title": item["name"], "items": item["reel"],
                                        "effects": item.get("effects") or {}}, ensure_ascii=False),
                            encoding="utf-8")
            args = ["--config", str(cfg), "reel", str(spec)]
        else:
            args = ["--config", str(cfg), "run", item["path"], item["steamid"]]
            if item.get("rounds"):
                args += ["--rounds", rounds_spec(item["rounds"])]
        if os.environ.get("POVFORGE_PLACEHOLDER"):  # testing without CS2
            args.append("--placeholder")
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        self.proc = subprocess.Popen(cli_command(*args), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace", env=env,
                                     creationflags=flags)
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()

    def _read(self, proc=None) -> None:
        proc = self.proc if proc is None else proc
        assert proc and proc.stdout
        for raw in proc.stdout:
            line = raw.rstrip()
            if line:
                self._take(line, proc)
        code = proc.wait()
        with self.lock:
            if self.proc is not proc:
                return
            if self.state == "running":
                if code == 0 and self.result:
                    self.state, self.stage = "done", "done"
                else:
                    self.state = "error"
                    self.error = self.error or (self.lines[-1] if self.lines else f"Exit code {code}")
        self._notify_finished(proc)

    def _notify_finished(self, proc) -> None:
        with self.lock:
            if (self.proc is not proc or self.cancelling or self._finish_notified
                    or proc.poll() is None):
                return
            self._finish_notified = True
        if self.on_finish:
            self.on_finish()

    def _take(self, line: str, proc=None) -> None:
        with self.lock:
            if proc is not None and self.proc is not proc:
                return
            self.lines.append(line)
            if m := re.match(r"Starting CS2 .* record (\d+) clips", line):
                self.stage, self.step = "record", (0, int(m.group(1)))
            elif m := re.match(r"Camera recording \d+/\d+: (\d+) extra shots", line):
                self.stage, self.step = "record", (0, int(m.group(1)))
            elif m := re.match(r"Recorded shot_[A-Za-z0-9_-]+ \((\d+)/(\d+)\)", line):
                self.stage, self.step = "record", (int(m.group(1)), int(m.group(2)))
            elif m := re.match(r"Recorded r(\d+) \((\d+)/(\d+)\)", line):
                self.stage = "record"
                self.recorded.append(int(m.group(1)))
                self.step = (int(m.group(2)), int(m.group(3)))
            elif m := re.match(r"Overlays (\d+)/(\d+)", line):
                self.stage, self.step = "overlays", (int(m.group(1)), int(m.group(2)))
            elif line.startswith(("Taking a screenshot", "Making intro")):
                self.stage, self.step = "intro", (0, 0)
            elif m := re.match(r"Composing (\d+)/(\d+)", line):
                self.stage, self.step = "compose", (int(m.group(1)), int(m.group(2)))
            elif line.startswith("Joining parts"):
                self.stage, self.step = "compose", (1, 1)
            elif line.startswith(("Cutting the highlights", "Making the cover")):
                self.stage, self.step = "extras", (0, 0)
            elif line.startswith("Highlights: "):
                self.highlights = line[12:].strip()
            elif line.startswith("Cover: "):
                self.cover = line[7:].strip()
            elif line.startswith("Description: "):
                self.description = line[13:].strip()
                try:
                    self.title = Path(self.description).read_text(encoding="utf-8").splitlines()[0]
                except Exception:
                    self.title = ""
            elif m := re.match(r"Reel source (\d+)/(\d+)", line):
                self.stage, self.step = "read", (0, 0)
                self.source = (int(m.group(1)), int(m.group(2)))
                self.recorded = []
            elif m := re.match(r"(?:Cutting the reel|Effects: moment|Camera editing) (\d+)/(\d+)", line):
                self.stage, self.step = "cut", (int(m.group(1)), int(m.group(2)))
            elif line.startswith(("Joining the reel", "Effects: joining", "Effects: sound")):
                self.stage, self.step = "cut", (1, 1)
            elif line.startswith("Done: "):
                self.result = line[6:].strip()
            elif line.startswith("Error: "):
                self.error = line[7:].strip()

    def cancel(self) -> None:
        with self.lock:
            if self.state != "running" or not self.proc or self.cancelling:
                return
            proc = self.proc
            self.cancelling = True
            self.state = "cancelled"
        try:
            self._cancel_process(proc)
        finally:
            with self.lock:
                self.cancelling = False
            self._notify_finished(proc)

    def _cancel_process(self, proc) -> None:
        from .. import hlae, settings_guard
        try:
            if sys.platform == "win32":
                # Stop preparation first, so it cannot launch a game after the
                # ownership check. A historical backup does not authorize this job.
                flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                subprocess.run(["taskkill", "/pid", str(proc.pid), "/t", "/f"],
                               capture_output=True, creationflags=flags)
                if settings_guard.owned_by(proc.pid):
                    subprocess.run(["taskkill", "/im", "cs2.exe", "/f"], capture_output=True, creationflags=flags)
            else:
                proc.terminate()
        except OSError as e:
            self._take(f"Could not stop the recording process: {e}")
        owns_game = settings_guard.owned_by(proc.pid)
        for _ in range(20):
            if (not owns_game or "cs2.exe" not in hlae.running_processes()) and proc.poll() is not None:
                break
            time.sleep(0.5)
        if (owns_game and "cs2.exe" in hlae.running_processes()) or proc.poll() is None:
            self._take("Error: The recording process or CS2 is still open. Your settings backup is kept. "
                       "Close both, then run: povforge restore-settings")
            return
        if not owns_game:
            if settings_guard.pending():
                self._take("Error: An earlier CS2 settings backup is still pending. "
                           "Close CS2, then run: povforge restore-settings")
            else:
                self._take("Cancelled before recording; no CS2 settings were changed.")
            return
        try:
            changed = settings_guard.restore()
            if settings_guard.pending():
                self._take("Error: Your CS2 settings could not be fully restored. "
                           "Run: povforge restore-settings")
            else:
                self._take(f"Your CS2 settings are back as before ({changed} file(s) put back).")
        except Exception as e:
            self._take(f"Error: Could not restore your CS2 settings ({e}). "
                       "Run: povforge restore-settings")


class Queue:
    """Recordings waiting their turn; runs them one after another through Job."""

    def __init__(self, job: Job, prefs: dict, *, store: Path | None = None):
        from .. import queue_store
        self.job, self.prefs = job, prefs
        self.lock = threading.Lock()
        self.store = store
        self.items, self.save_error = queue_store.load(store)
        self.next_id = max((i['id'] for i in self.items), default=0) + 1
        self.recovered = any(i['state']=='queued' for i in self.items)
        self.paused = self.recovered
        job.on_finish = self._finished

    def _save(self):
        from ..queue_store import save
        self.save_error = save(self.store, self.items)

    def snapshot(self) -> dict:
        with self.lock:
            return {"items": [dict(i) for i in self.items], "paused": self.paused,
                    "recovered": self.recovered, "save_error": self.save_error}

    def add(self, path: str, steamid: str, name: str, rounds: list[int], map_pretty: str) -> dict:
        return self._add({"kind": "match", "path": path, "steamid": steamid, "name": name, "rounds": rounds,
                          "map": map_pretty})

    def add_reel(self, title: str, items: list[dict], summary: str = "", fx: dict | None = None) -> dict:
        """A highlight reel: items are {demo, steamid, round} in the order they appear;
        ``fx`` the effects chosen for it (see effects.py)."""
        from .. import effects
        from ..reel import ReelItem
        reel = [{"demo": str(i["demo"]), "steamid": str(i["steamid"]), "round": int(i["round"]),
                 "name": str(i.get("name") or ""), "mode": str(i.get("mode", "kills")),
                 "opponent": str(i.get("opponent", "")), "weapons": i.get('weapons', [])} for i in items]
        for i in reel:
            i['weapons'] = list(ReelItem(**{k: v for k, v in i.items() if k != "name"}).weapons)
        if not reel:
            raise ValueError("No rounds in the reel.")
        return self._add({"kind": "reel", "name": title or "Highlights", "reel": reel, "rounds": [],
                          "path": "", "steamid": "", "map": summary, "effects": effects.normalize(fx)})

    def _add(self, fields: dict) -> dict:
        from ..queue_store import settings
        with self.lock:
            item = {"id": self.next_id, **fields, "state": "queued", "result": "", "highlights": "",
                    "cover": "", "description": "", "title": "", "error": "",
                    "settings": settings(self.prefs)}
            self.next_id += 1
            self.items.append(item)
            if not self.recovered:
                self.paused = False
            self._save()
        self._start_next()
        return item

    def _start_next(self) -> None:
        with self.lock:
            if (self.paused or getattr(self.job, "busy", self.job.state == "running")
                    or any(i["state"] == "running" for i in self.items)):
                return
            item = next((i for i in self.items if i["state"] == "queued"), None)
            if item is None:
                return
            item["state"] = "running"
            from ..recordings import signature
            from ..queue_store import settings
            task_prefs = {**self.prefs, **settings(item.get('settings', {}))}
            mode = (item.get('reel') or [{}])[0].get('mode', 'kills') if item.get('kind') == 'reel' else 'match'
            item['_record_profile'] = signature(task_prefs, mode)
            self._save()
        try:
            self.job.start({**item, '_live_prefs':self.prefs}, task_prefs)
        except Exception as e:
            with self.lock:
                item["state"], item["error"] = "error", str(e)
                self._save()

    def _finished(self) -> None:
        snap = self.job.snapshot()
        with self.lock:
            item = next((i for i in self.items if i["id"] == snap["item"]), None)
            if item is not None:
                item["state"] = snap["state"]
                for k in ("result", "highlights", "cover", "description", "title", "error"):
                    item[k] = snap[k]
            if snap["state"] == "cancelled":
                self.paused = True       # stopping one recording pauses the rest
            completed = dict(item) if item is not None and snap['state'] == 'done' else None
            self._save()
        if completed:
            from ..recordings import remember
            if completed.get('kind') == 'reel':
                known = _known_demos()
                metadata = [known.get(i['demo']) for i in completed.get('reel', [])] if isinstance(known,dict) else []
                completed['maps'] = list(dict.fromkeys(m['map'] for m in metadata
                    if isinstance(m,dict) and isinstance(m.get('map'),str) and m['map']))
            remember(app_dir(), completed, self.prefs, snap.get('elapsed', 0))
        self._start_next()

    def resume(self) -> None:
        with self.lock:
            self.paused = False
            self.recovered = False
            self._save()
        self._start_next()

    def retry(self, item_id: int) -> None:
        with self.lock:
            for i in self.items:
                if i["id"] == item_id and i["state"] in ("error", "cancelled"):
                    i["state"], i["error"] = "queued", ""
            self.paused = False
            self.recovered = False
            self._save()
        self._start_next()

    def remove(self, item_id: int) -> None:
        with self.lock:
            self.items = [i for i in self.items if i["id"] != item_id or i["state"] == "running"]
            self._save()

    def clear_finished(self) -> None:
        with self.lock:
            self.items = [i for i in self.items if i["state"] in ("queued", "running")]
            self._save()


# --- updates -----------------------------------------------------------------------------

RELEASES_API = "https://api.github.com/repos/Chester-chs/CS2-povforge/releases/latest"
RELEASES_PAGE = "https://github.com/Chester-chs/CS2-povforge/releases/latest"


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


DOWNLOADS = "https://github.com/Chester-chs/CS2-povforge/releases/download/"
SETUP_ASSET = "PovForge-Setup.exe"
FILES_ASSET = "PovForge-windows.zip"     # the whole app, file by file: updates fetch only what changed


def _plain_notes(md: str, limit: int = 900) -> str:
    """Release notes as plain text for the update sheet."""
    md = re.split(r"(?m)^\*\*Windows", md or "")[0]                # what's new only, not install help
    md = re.sub(r"(?m)^\*\*What's new.*\n", "", md)
    md = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", md)             # [text](url) -> text
    md = md.replace("**", "").replace("`", "").replace("\r", "")
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    return md if len(md) <= limit else md[:limit].rsplit("\n", 1)[0] + "\n…"


def latest_release() -> dict:
    """The newest release: version, page, installer url/size/sha256, notes. Raises on failure."""
    import urllib.request
    try:
        req = urllib.request.Request(RELEASES_API, headers={"User-Agent": "PovForge",
                                                           "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
        tag = data.get("tag_name", "")
        info = {"version": tag.lstrip("v"), "url": data.get("html_url", RELEASES_PAGE),
                "notes": _plain_notes(data.get("body", "")), "setup": "", "size": 0, "sha256": ""}
        for a in data.get("assets", []):
            if a.get("name") == FILES_ASSET:
                info["zip"] = a.get("browser_download_url", "")
            if a.get("name") == SETUP_ASSET:
                info["setup"] = a.get("browser_download_url", "")
                info["size"] = int(a.get("size") or 0)
                digest = a.get("digest") or ""
                if digest.startswith("sha256:"):
                    info["sha256"] = digest[7:].lower()
    except Exception:
        # API blocked or rate-limited: the release page redirects to the newest tag
        req = urllib.request.Request(RELEASES_PAGE, headers={"User-Agent": "PovForge"})
        with urllib.request.urlopen(req, timeout=10) as r:
            url = r.geturl()
        tag = url.rstrip("/").rsplit("/", 1)[-1]
        if not tag.startswith("v"):
            raise RuntimeError("Couldn't find the latest release.")
        info = {"version": tag.lstrip("v"), "url": url, "notes": "",
                "setup": f"{DOWNLOADS}{tag}/{SETUP_ASSET}", "size": 0, "sha256": "",
                "zip": f"{DOWNLOADS}{tag}/{FILES_ASSET}"}
    if not info["setup"].startswith(DOWNLOADS):
        info["setup"] = ""        # only ever download our own release assets
    if not info.get("zip", "").startswith(DOWNLOADS):
        info["zip"] = ""
    return info


def check_update(current: str) -> dict | None:
    """Newest release on GitHub if it's newer than this one (quietly None on any problem)."""
    try:
        info = latest_release()
    except Exception:
        return None
    if info["version"] and _version_tuple(info["version"]) > _version_tuple(current):
        return info
    return None


def can_self_update() -> bool:
    """Only the installed Windows app can update itself (it was put there by the installer)."""
    return sys.platform == "win32" and getattr(sys, "frozen", False) and \
        (Path(sys.executable).parent / "unins000.exe").is_file()


class Updater:
    """Check for a new version, download its installer, run it quietly and quit.
    The installer closes this app, installs over it and opens the new version."""

    def __init__(self, current: str, busy, quit_app):
        self.current, self.busy, self.quit_app = current, busy, quit_app
        self.lock = threading.Lock()
        self.state, self.info, self.error, self.fraction, self.done_mb = "idle", None, "", -1.0, 0
        self.total_mb = 0

    def status(self) -> dict:
        with self.lock:
            return self.status_unlocked()

    def check(self) -> dict:
        with self.lock:
            if self.state in ("downloading", "installing"):
                return self.status_unlocked()
            self.state, self.error = "checking", ""
        try:
            info = latest_release()
            newer = bool(info["version"]) and _version_tuple(info["version"]) > _version_tuple(self.current)
            with self.lock:
                self.info = info if newer else None
                self.state = "available" if newer else "current"
        except Exception as e:
            with self.lock:
                self.state, self.error = "error", f"{e}"
        return self.status()

    def status_unlocked(self) -> dict:
        return {"state": self.state, "current": self.current, "info": self.info, "error": self.error,
                "fraction": self.fraction, "done_mb": self.done_mb, "total_mb": self.total_mb,
                "can_install": can_self_update() or bool(os.environ.get("POVFORGE_PLACEHOLDER"))}

    def install(self) -> dict:
        with self.lock:
            fresh = self.state not in ("available", "downloading", "installing")
        if fresh:                       # not looked up by this updater yet (or a while ago): do it now
            self.check()
        with self.lock:
            if self.state in ("downloading", "installing"):
                return self.status_unlocked()
            if self.state != "available" or not self.info or not self.info.get("setup"):
                if self.state == "available":
                    self.state, self.error = "error", "This release has no installer to download."
                return self.status_unlocked()
            if self.busy():
                self.error = "busy"
                return self.status_unlocked()
            self.state, self.error, self.fraction, self.done_mb = "downloading", "", 0.0, 0
        threading.Thread(target=self._work, daemon=True).start()
        return self.status()

    def _work(self) -> None:
        info = self.info or {}
        if info.get("zip") and can_self_update():
            try:
                self._delta(info)
                return
            except Exception as e:          # fall back to the full installer
                print(f"Incremental update failed, using the installer: {e}", flush=True)
                with self.lock:
                    self.state, self.fraction, self.done_mb, self.total_mb = "downloading", 0.0, 0, 0
        self._full(info)

    def _delta(self, info: dict) -> None:
        """Download only the files that changed, swap them in after quitting."""
        from .. import selfupdate

        def progress(done: int, total: int) -> None:
            with self.lock:
                self.done_mb, self.total_mb = done >> 20, max(1, round(total / 1048576))
                self.fraction = done / total if total else -1.0
        work = app_dir() / "update"
        plan = selfupdate.prepare(selfupdate.app_dir(), info["zip"], self.current, work, progress)
        print(f"Update {self.current} -> {plan['version']}: {len(plan['changed'])} file(s), "
              f"{plan['bytes'] / 1048576:.1f} MB", flush=True)
        with self.lock:
            self.state, self.fraction = "installing", 1.0
        selfupdate.apply(selfupdate.app_dir(), work, plan, app_dir() / "update.log", wait_pid=os.getpid())
        time.sleep(1.5)                     # let the page hear "installing" first
        self.quit_app()

    def _full(self, info: dict) -> None:
        import hashlib
        import tempfile
        import urllib.request
        try:
            folder = Path(tempfile.mkdtemp(prefix="povforge-update-"))
            dest = folder / f"PovForge-Setup-{info['version']}.exe"
            h = hashlib.sha256()
            req = urllib.request.Request(info["setup"], headers={"User-Agent": "PovForge"})
            with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
                total = int(r.headers.get("Content-Length") or info.get("size") or 0)
                done = 0
                while chunk := r.read(1 << 20):
                    f.write(chunk)
                    h.update(chunk)
                    done += len(chunk)
                    with self.lock:
                        self.done_mb = done >> 20
                        self.fraction = done / total if total else -1.0
            if info.get("size") and done != info["size"]:
                raise RuntimeError("The download is incomplete. Try again.")
            if info.get("sha256") and h.hexdigest() != info["sha256"]:
                raise RuntimeError("The download doesn't match the release (checksum differs). Try again.")
            with self.lock:
                self.state, self.fraction = "installing", 1.0
            if os.environ.get("POVFORGE_PLACEHOLDER") and not can_self_update():
                return                      # test mode: stop before running anything
            run_installer(dest)
            time.sleep(1.5)                 # let the page hear "installing" first
            self.quit_app()
        except Exception as e:
            with self.lock:
                self.state, self.error = "error", str(e)


def run_installer(setup: Path) -> None:
    """Start the installer on its own (it must outlive this app). /SILENT shows only a
    progress window; /update=1 makes it open the new PovForge when it's done."""
    flags = 0x00000008 | 0x00000200          # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen([str(setup), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS", "/update=1"],
                     creationflags=flags, close_fds=True, cwd=str(setup.parent))


# --- setup (HLAE, FFmpeg, CS2) ------------------------------------------------------

class Setup:
    def __init__(self):
        self.lock = threading.Lock()
        self.installing = ""
        self.message = ""
        self.fraction = -1.0
        self.error = ""

    def status(self) -> dict:
        from .. import hlae, settings_guard, tools
        from ..config import Config
        cfg = Config()
        out = {"windows": sys.platform == "win32" or bool(os.environ.get("POVFORGE_PLACEHOLDER")),
               "placeholder": bool(os.environ.get("POVFORGE_PLACEHOLDER")), "problems": []}

        def check(key, fn, default=""):
            try:
                out[key] = fn()
            except Exception as e:  # each check on its own: one failure mustn't blank the panel
                out[key] = default
                if not isinstance(e, RuntimeError):
                    out["problems"].append(f"{key}: {e}")

        check("hlae", lambda: str(hlae.find_hlae(cfg.record)))
        check("ffmpeg", lambda: tools.find_ffmpeg() or "")
        check("ffmpeg_bundled", lambda: bool(tools.bundled_ffmpeg()), False)
        check("cs2", lambda: str(hlae.find_cs2(cfg.record)) if sys.platform == "win32" else "")
        check("procs", lambda: sorted(hlae.running_processes()), [])
        procs = set(out.pop("procs"))
        out["anticheat"] = sorted({n for exe, n in hlae.ANTI_CHEAT.items() if exe in procs})
        out["cs2_running"] = "cs2.exe" in procs
        out["steam_running"] = "steam.exe" in procs if sys.platform == "win32" else True
        check("settings_pending", settings_guard.pending, False)
        with self.lock:
            out["installing"], out["message"] = self.installing, self.message
            out["fraction"], out["install_error"] = self.fraction, self.error
        return out

    def install(self, what: str) -> None:
        from .. import tools
        with self.lock:
            if self.installing:
                return
            self.installing, self.message, self.fraction, self.error = what, "", -1.0, ""

        def progress(msg: str, frac: float) -> None:
            with self.lock:
                self.message, self.fraction = msg, frac

        def work() -> None:
            try:
                for w in (["hlae", "ffmpeg"] if what == "all" else [what]):
                    if w == "hlae" and not self.status()["hlae"]:
                        tools.install_hlae(progress)
                    if w == "ffmpeg" and not tools.find_ffmpeg():
                        tools.install_ffmpeg(progress)
            except Exception as e:
                with self.lock:
                    self.error = str(e)
            finally:
                with self.lock:
                    self.installing = ""

        threading.Thread(target=work, daemon=True).start()


# --- desktop helpers -------------------------------------------------------------------

def open_path(path: str, select: bool = False) -> None:
    p = Path(path)
    if sys.platform == "win32":
        # Explorer does the opening (with the default app): it is always running, so
        # the start isn't lost when this request's thread ends straight afterwards
        if select:
            subprocess.Popen(["explorer", "/select,", str(p)])
        else:
            subprocess.Popen(["explorer", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p.parent if select else p)])


FILE_KINDS = {
    "demo": ("CS2 demo", "*.dem *.zst *.gz *.bz2"),
    "video": ("Video", "*.mp4 *.mov *.mkv *.webm *.avi *.flv *.m4v"),
    "audio": ("Music", "*.mp3 *.m4a *.aac *.wav *.flac *.ogg *.opus *.mp4"),
}


def pick_file(initial: str, kind: str = "demo") -> str | None:
    """Native file dialog (tkinter); runs on its own thread so the server keeps going."""
    result: list[str | None] = [None]
    label, pattern = FILE_KINDS.get(kind, FILE_KINDS["demo"])

    def ask() -> None:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            result[0] = filedialog.askopenfilename(
                title=label, initialdir=initial,
                filetypes=[(label, pattern), ("All files", "*.*")]) or None
            root.destroy()
        except Exception:
            result[0] = None

    t = threading.Thread(target=ask)
    t.start()
    t.join()
    return result[0]


def pick_folder(initial: str) -> str | None:
    result: list[str | None] = [None]

    def ask() -> None:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            result[0] = filedialog.askdirectory(initialdir=initial) or None
            root.destroy()
        except Exception:
            result[0] = None

    t = threading.Thread(target=ask)
    t.start()
    t.join()
    return result[0]


# --- HTTP ------------------------------------------------------------------------------

class App:
    def __init__(self):
        self.references = ReferenceLibrary()
        self.prefs = load_prefs()
        if self.prefs.get("folders_set") and self.prefs.get("by_player", True) and not self.prefs.get("organized"):
            try:
                organize_existing(self.prefs)
            except Exception as e:
                print(f"Sorting the videos by player failed: {e}", flush=True)
            save_prefs(self.prefs)
        self.job = Job()
        self.queue = Queue(self.job, self.prefs, store=app_dir() / 'queue.json')
        self.setup = Setup()
        self.update: dict | None = None
        self.quit = lambda: None            # set by main() once the server exists
        self.updater = Updater(__version__, busy=lambda: self.job.busy or self.inspecting > 0,
                               quit_app=lambda: self.quit())
        self.last_seen = time.time()   # the page asks for state every second or two
        self.bye_at = 0.0              # the page said it was closing (pagehide)
        self.window = None             # native window lifetime, or the owned browser process
        self.inspecting = 0
        self.screen = screen_size()
        threading.Thread(target=self._check_update, daemon=True).start()

    def _check_update(self) -> None:
        # through the updater, so "Update" works straight away from what this found
        st = self.updater.check()
        self.update = st["info"] if st["state"] == "available" else None

    def busy(self) -> bool:
        return (self.job.busy or bool(self.setup.installing) or self.inspecting > 0
                or self.updater.status()["state"] in ("downloading", "installing"))

    def quit_reason(self, now: float) -> str:
        """Why the app should close now ('' = keep running). The window is what
        counts: while it's open the app stays, however rarely a hidden or
        minimised page gets to check in (browsers slow those pages down)."""
        if self.busy():
            return ""
        if self.bye_at and self.last_seen <= self.bye_at and now - self.bye_at > 8:
            return "window closed"
        if self.window is not None:
            if self.window.poll() is None:
                return ""
            return "window closed" if now - self.last_seen > 10 else ""
        return "no window for 3 minutes" if now - self.last_seen > 180 else ""


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        csrf_token = secrets.token_urlsafe(32)

        def log_message(self, *a):  # quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data, code: int = 200) -> None:
            self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json")

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(n) or b"{}") if n else {}

        def _valid_host(self) -> bool:
            # Compare with the socket we actually bound, never a client-supplied origin.
            address, port = self.server.server_address[:2]
            allowed = {f"{address}:{port}"}
            if address == "127.0.0.1":
                allowed.add(f"localhost:{port}")
            hosts = self.headers.get_all("Host", []) if hasattr(self.headers, "get_all") else [self.headers.get("Host", "")]
            return len(hosts) == 1 and hosts[0] in allowed

        def _same_origin(self) -> bool:
            origin = self.headers.get("Origin")
            return (self._valid_host() and (origin is None or origin == f"http://{self.headers.get('Host')}")
                    and secrets.compare_digest(self.headers.get("X-Povforge-Token", ""), self.csrf_token))

        def do_GET(self) -> None:
            if not self._valid_host():
                return self._json({"error": "Forbidden host."}, 403)
            url = urlparse(self.path)
            q = parse_qs(url.query)
            try:
                if url.path == "/":
                    page = (STATIC / "index.html").read_text(encoding="utf-8")
                    return self._send(200, page.replace("__POVFORGE_TOKEN__", self.csrf_token).encode("utf-8"),
                                      "text/html; charset=utf-8")
                if url.path.startswith("/static/"):
                    f = (STATIC / url.path[len("/static/"):]).resolve()
                    if STATIC.resolve() in f.parents and f.is_file():
                        return self._file(f)
                    return self._send(404, b"not found", "text/plain")
                if url.path.startswith("/api/"):
                    app.last_seen = time.time()
                if url.path == "/api/state":
                    from .. import effects
                    return self._json({"version": __version__, "prefs": app.prefs, "update": app.update,
                                       "setup": app.setup.status(), "job": app.job.snapshot(),
                                       "queue": app.queue.snapshot(),
                                       "screen": app.screen, "sizes": fitting_sizes(app.screen),
                                       "effects": {"defaults": effects.DEFAULTS, "presets": effects.PRESETS,
                                                   "transitions": list(effects.TRANSITIONS),
                                                   "grades": [g for g in effects.GRADES if g != "match"]}})
                if url.path == "/api/style/video":
                    return self._video(Path(app.references.get((q.get("id") or [""])[0])["preview"]))
                if url.path == "/api/job":
                    return self._json({**app.job.snapshot(), "queue": app.queue.snapshot()})
                if url.path == "/api/workfiles":
                    d = work_dir(app.prefs)
                    return self._json({"path": str(d), "bytes": folder_size(d) if d.is_dir() else 0})
                if url.path == "/api/update":
                    return self._json(app.updater.status())
                if url.path == "/api/setup":
                    return self._json(app.setup.status())
                if url.path == "/api/demos":
                    return self._json(find_demos(app.prefs["demo_folders"]))
                if url.path == '/api/library':
                    from ..recordings import list_videos
                    return self._json(list_videos(app_dir(), app.prefs))
                if url.path == "/api/map-thumbnail":
                    from ..maps import get_map_thumbnail
                    try:
                        thumbnail = get_map_thumbnail((q.get("map") or [""])[0])
                    except (ValueError, OSError):
                        return self._send(404, b"thumbnail unavailable", "text/plain")
                    return self._file(thumbnail)
                if url.path == "/api/radar":
                    from ..maps import get_map
                    name = re.sub(r"[^a-z0-9_]", "", (q.get("map") or [""])[0].lower())
                    return self._file(get_map(name).radar)
                if url.path == "/api/thumb":
                    p = Path((q.get("path") or [""])[0]).resolve()
                    root = Path(app.prefs["output"]).resolve()
                    if root in p.parents and p.suffix.lower() in (".png", ".jpg") and p.is_file():
                        return self._file(p)
                    return self._send(404, b"not found", "text/plain")
                self._send(404, b"not found", "text/plain")
            except Exception as e:
                self._json({"error": str(e)}, 500)

        def do_POST(self) -> None:
            if not self._same_origin():
                return self._json({"error": "Request rejected. Reopen PovForge and try again."}, 403)
            url = urlparse(self.path)
            try:
                b = self._body()
                if url.path == "/api/bye":
                    app.bye_at = time.time()
                    return self._json({"ok": True})
                if url.path == "/api/window-theme":
                    if type(b.get("dark")) is not bool:
                        return self._json({"error": "Invalid theme"}, 400)
                    from . import window_chrome
                    return self._json({"applied": window_chrome.apply(getattr(app, "window", None), b["dark"])})
                if url.path == "/api/inspect":
                    path = b.get("path", "")
                    if not is_demo(Path(path)):
                        return self._json({"error": "not_a_demo"}, 400)
                    app.inspecting += 1
                    try:
                        return self._json(inspect_isolated(path, Path(app.prefs["output"]), details=True))
                    finally:
                        app.inspecting -= 1
                        app.last_seen = time.time()
                if url.path == "/api/browse":
                    folder = (app.prefs["demo_folders"] or [str(Path.home())])[0]
                    return self._json({"path": pick_file(folder)})
                if url.path == "/api/pick":
                    kind = b.get("kind") if b.get("kind") in FILE_KINDS else "video"
                    start = str(Path(app.prefs["output"]) if kind == "video" else Path.home() / "Music")
                    if not Path(start).is_dir():
                        start = str(Path.home())
                    return self._json({"path": pick_file(start, kind)})
                if url.path == "/api/style/analyze":
                    app.inspecting += 1
                    try:
                        return self._json(analyze_isolated(b.get("path", "")))
                    finally:
                        app.inspecting -= 1
                        app.last_seen = time.time()

                if url.path in ("/api/style/prepare", "/api/style/propose"):
                    app.inspecting += 1
                    try:
                        if url.path.endswith("prepare"):
                            return self._json(app.references.prepare(str(b.get("path", ""))))
                        ref = app.references.get(str(b.get("id", "")))
                        return self._json(reference_isolated("analyze", ref["source"],
                            "--start", str(b.get("start", 0)), "--end", str(b.get("end", 0)),
                            "--kind", str(b.get("kind", "auto")), "--description", str(b.get("description", ""))[:500],
                            owner=app.references))
                    finally:
                        app.inspecting -= 1
                        app.last_seen = time.time()

                if url.path == "/api/folder":
                    which = b.get("which")
                    initial = app.prefs["output"] if which == "output" else app.prefs["demo_folders"][0]
                    chosen = pick_folder(initial)
                    if chosen:
                        if which == "output":
                            app.prefs["output"] = chosen
                        else:
                            app.prefs["demo_folders"] = [chosen] + [f for f in app.prefs["demo_folders"]
                                                                      if f != chosen][:4]
                        save_prefs(app.prefs)
                    return self._json(app.prefs)
                if url.path == "/api/player-output":
                    if app.job.busy:
                        return self._json({"error": "busy"}, 409)
                    sid = b.get("steamid")
                    if not isinstance(sid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", sid):
                        return self._json({"error": "invalid player"}, 400)
                    name = str(b.get("name") or sid)[:128]
                    entry = app.prefs.get("player_folders", {}).get(sid, {})
                    if b.get("reset") is True:
                        entry.pop("path", None)
                    else:
                        initial = entry.get("path") or str(Path(app.prefs["output"]) / entry.get("folder", folder_name(name)))
                        chosen = pick_folder(initial)
                        if not chosen:
                            return self._json(app.prefs)
                        selected = Path(chosen)
                        if not selected.is_absolute() or not selected.is_dir():
                            return self._json({"error": "invalid folder"}, 400)
                        player_folder(app.prefs, sid, name)
                        app.prefs["player_folders"][sid]["path"] = str(selected.resolve())
                    save_prefs(app.prefs)
                    return self._json(app.prefs)
                if url.path == "/api/player-folder":
                    if app.job.busy:
                        return self._json({"error": "busy"}, 409)
                    rename_player_folder(app.prefs, str(b.get("steamid", "")), str(b.get("folder", "")))
                    save_prefs(app.prefs)
                    return self._json(app.prefs)
                if url.path == "/api/folders/confirm":
                    app.prefs["folders_set"] = True
                    save_prefs(app.prefs)
                    return self._json(app.prefs)
                if url.path == "/api/prefs":
                    for k in ("intro", "minimap", "keyboard", "show_enemies", "lang", "upload"):
                        if k in b:
                            app.prefs[k] = b[k]
                    if isinstance(b.get("music_library"), list):
                        app.prefs["music_library"] = [{"path": str(m.get("path") or ""), "name": str(m.get("name") or "")[:80]}
                                                      for m in b["music_library"][:50]
                                                      if isinstance(m, dict) and m.get("path")]
                    if "by_player" in b:
                        app.prefs["by_player"] = bool(b["by_player"])
                    app.prefs["record_res"] = "1080"
                    if type(b.get("record_fps")) is int and b["record_fps"] in FRAME_RATES:
                        app.prefs["record_fps"] = b["record_fps"]
                    app.prefs.pop("upload_4k", None)
                    update_appearance(app.prefs, b)
                    if "reel_fx" in b:
                        from .. import effects
                        app.prefs["reel_fx"] = effects.normalize(b["reel_fx"])
                    if isinstance(b.get("fx_presets"), list):
                        from .. import effects
                        app.prefs["fx_presets"] = [{"name": str(x.get("name") or "")[:40],
                                                    "fx": effects.normalize(x.get("fx")),
                                                    "source": str(x.get("source") or "")[:200]}
                                                   for x in b["fx_presets"][:30]
                                                   if isinstance(x, dict) and str(x.get("name") or "").strip()]
                    save_prefs(app.prefs)
                    return self._json(app.prefs)
                if url.path in ("/api/run", "/api/queue/add"):
                    app.queue.add(b["path"], b["steamid"], b.get("name", ""),
                                  [int(r) for r in b.get("rounds") or []], b.get("map", ""))
                    return self._json({**app.job.snapshot(), "queue": app.queue.snapshot()})
                if url.path == "/api/queue/add-reel":
                    app.queue.add_reel(b.get("title", ""), b.get("items") or [], b.get("summary", ""),
                                       b.get("effects"))
                    return self._json({**app.job.snapshot(), "queue": app.queue.snapshot()})
                if url.path == "/api/queue/remove":
                    app.queue.remove(int(b.get("id", 0)))
                    return self._json(app.queue.snapshot())
                if url.path == "/api/queue/clear":
                    app.queue.clear_finished()
                    return self._json(app.queue.snapshot())
                if url.path == "/api/queue/resume":
                    app.queue.resume()
                    return self._json(app.queue.snapshot())
                if url.path == "/api/queue/retry":
                    app.queue.retry(int(b.get("id", 0)))
                    return self._json(app.queue.snapshot())
                if url.path == "/api/open-url":
                    u = b.get("url", "")
                    if u.startswith("https://github.com/Chester-chs/"):
                        webbrowser.open(u)
                    return self._json({"ok": True})
                if url.path == "/api/cancel":
                    app.job.cancel()
                    return self._json(app.job.snapshot())
                if url.path == "/api/reset":
                    if not app.job.busy:
                        app.job.reset()
                    return self._json(app.job.snapshot())
                if url.path == "/api/workfiles/clean":
                    if app.job.busy or any(i["state"] in ("queued", "running") for i in app.queue.snapshot()["items"]):
                        return self._json({"error": "busy"}, 409)
                    freed = clean_work(app.prefs)
                    return self._json({"freed": freed, "bytes": 0, "path": str(work_dir(app.prefs))})
                if url.path == "/api/update/check":
                    st = app.updater.check()
                    app.update = st["info"] if st["state"] == "available" else app.update
                    return self._json(st)
                if url.path == "/api/update/install":
                    return self._json(app.updater.install())
                if url.path == "/api/install":
                    app.setup.install(b.get("what", "all"))
                    return self._json(app.setup.status())
                if url.path == "/api/restore-settings":
                    try:
                        app.job.restore_settings()
                    except RuntimeError as e:
                        return self._json({"error": str(e)}, 409)
                    return self._json(app.setup.status())
                if url.path == "/api/open":
                    p = b.get("path", "")
                    if not p or not Path(p).exists():
                        print(f"Open: not found: {p!r}", flush=True)
                        return self._json({"error": "missing"}, 404)
                    try:
                        open_path(p, bool(b.get("select")))
                    except Exception as e:
                        print(f"Open: {p!r} failed: {e}", flush=True)
                        raise
                    return self._json({"ok": True})
                self._send(404, b"not found", "text/plain")
            except Exception as e:
                self._json({"error": str(e)}, 500)

        def _file(self, f: Path) -> None:
            self._send(200, Path(f).read_bytes(), CONTENT_TYPES.get(Path(f).suffix.lower(), "application/octet-stream"))

        def _video(self, path: Path) -> None:
            from ..reference import byte_range
            size = path.stat().st_size
            header = self.headers.get("Range")
            try:
                start, end = byte_range(header, size) if header else (0, size - 1)
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(206 if header else 200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(end - start + 1))
            if header:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            try:
                with path.open("rb") as stream:
                    stream.seek(start)
                    left = end - start + 1
                    while left > 0:
                        chunk = stream.read(min(65536, left))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass

    return Handler


def open_window(url: str) -> subprocess.Popen | None:
    """An app-style window (no tabs or address bar) in Edge or Chrome, else the default browser."""
    if sys.platform == "win32":
        candidates = [
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe",
        ]
        for c in candidates:
            if c.is_file():
                profile = app_dir() / "window"
                # keep the page running normally when the window is hidden or behind others
                return subprocess.Popen([str(c), f"--app={url}", "--window-size=1280,820",
                                         f"--user-data-dir={profile}", "--no-first-run", *NO_THROTTLE])
    for name in ("microsoft-edge", "google-chrome", "chromium"):
        exe = shutil.which(name)
        if exe:
            return subprocess.Popen([exe, f"--app={url}", "--window-size=1280,820", *NO_THROTTLE])
    webbrowser.open(url)
    return None


NO_THROTTLE = ["--disable-background-timer-throttling", "--disable-renderer-backgrounding",
               "--disable-backgrounding-occluded-windows"]


def main(port: int = 0, open_browser: bool = True) -> None:
    app = App()
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"PovForge is running at {url} (close this window to quit)", flush=True)
    native = None
    if open_browser:
        from .native_window import create
        native = create(url)
        app.window = native or open_window(url)

    def quit_app():
        server.shutdown()
        if native is not None:
            native.close()
    app.quit = lambda: threading.Thread(target=quit_app, daemon=True).start()

    def watch() -> None:
        # a browser already running with our window profile takes the window over and
        # this process ends at once: then we can't watch the window, only the page
        time.sleep(6)
        if native is None and app.window is not None and app.window.poll() is not None:
            app.window = None
        while True:
            time.sleep(3)
            reason = app.quit_reason(time.time())
            if reason:
                print(f"Quitting: {reason}", flush=True)
                server.shutdown()
                return

    threading.Thread(target=watch, daemon=True).start()
    try:
        if native is None:
            server.serve_forever()
        else:
            # WebView2 owns the main UI thread; HTTP and recording keep their
            # existing background lifetimes, including finishing busy jobs.
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                native.run()
            except Exception as exc:
                print(f'Native window failed; using browser window: {exc}', flush=True)
                native = None
                app.window = open_window(url)
            worker.join()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        app.references.close()
