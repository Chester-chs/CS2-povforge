"""PovForge app: a small local web server plus a page that drives the pipeline.

Run with ``povforge gui`` (or the packaged PovForge.exe). It listens on
127.0.0.1 only and opens the page in an Edge/Chrome app window (falls back to
the default browser). Recording runs ``povforge run`` as a child process, so
the app shows the same steps and messages as the command line.
"""

from __future__ import annotations

import json
import os
import re
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


def load_prefs() -> dict:
    f = app_dir() / "app.json"
    prefs = {"output": str(default_output()), "demo_folders": [str(Path.home() / "Downloads")],
             "intro": True, "minimap": True, "keyboard": True, "show_enemies": False, "lang": "",
             "upload": True, "appearance": "auto", "accent": "blue"}
    if f.exists():
        try:
            prefs.update(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return prefs


def save_prefs(prefs: dict) -> None:
    app_dir().mkdir(parents=True, exist_ok=True)
    (app_dir() / "app.json").write_text(json.dumps(prefs, indent=2, ensure_ascii=False), encoding="utf-8")


def _toml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)  # a JSON string is a valid TOML basic string


def write_job_config(prefs: dict) -> Path:
    """povforge.toml for one run, from the app's switches."""
    lines = ["[output]", f"dir = {_toml_str(prefs['output'])}", "",
             "[overlay]", f"minimap = {str(bool(prefs['minimap'])).lower()}",
             f"keyboard = {str(bool(prefs['keyboard'])).lower()}",
             f"show_enemies = {str(bool(prefs['show_enemies'])).lower()}", "",
             "[intro]", f"enabled = {str(bool(prefs['intro'])).lower()}", "",
             "[highlights]", "enabled = false", "",      # highlights are made as a reel now
             "[upload]", f"enabled = {str(bool(prefs.get('upload', True))).lower()}", ""]
    f = app_dir() / "last-run.toml"
    app_dir().mkdir(parents=True, exist_ok=True)
    f.write_text("\n".join(lines), encoding="utf-8")
    return f


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
    from ..demo import load_demo, load_scoreboard, prepare_demo
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
    ends = [r.end_tick for r in d.rounds]
    starts = [0] + ends[:-1]

    def round_of(tick: int) -> int | None:
        for i, (a, b) in enumerate(zip(starts, ends)):
            if a < tick <= b:
                return i
        return None

    n = len(d.rounds)
    kills = {p.steamid: [0] * n for p in d.players}
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
    try:
        from ..demo import round_sides
        from ..highlights import round_table
        table = round_table(d.rounds, d.deaths, d.winners, round_sides(dem, d.rounds))
    except Exception:
        pass

    def per_round(sid: str) -> dict:
        rows = table.get(sid)
        if not rows:
            return {"rounds_k": kills.get(sid, []), "rounds_died": died.get(sid, []),
                    "rounds_hs": [0] * n, "rounds_clutch": [0] * n, "rounds_won": [None] * n}
        return {"rounds_k": [r.kills for r in rows], "rounds_died": died.get(sid, []),
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
    info = {"path": str(src), "name": src.name, "map": d.map_name, "map_pretty": pretty_map(d.map_name),
            "rounds": n, "minutes": round(d.last_tick / d.tickrate / 60, 1), "faceit_match": match_id(src.name),
            "date": time.strftime("%Y-%m-%d %H:%M", time.localtime(src.stat().st_mtime)), "teams": out_teams}
    _inspect_cache[key] = info
    score = f"{out_teams[0]['score']}:{out_teams[1]['score']}" if len(out_teams) >= 2 and out_teams[1]["score"] is not None else ""
    _remember_demo(str(src), info["map_pretty"], score)
    return info


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
            if self.state == "running":
                raise RuntimeError("A recording is already running.")
            self.reset()
            self.state, self.stage, self.started = "running", "read", time.time()
            self.player, self.demo, self.item, self.kind = item["name"], item.get("path", ""), item.get("id", 0), kind
            self.planned = sorted(item.get("rounds") or [])
        cfg = write_job_config(prefs)
        if kind == "reel":
            spec = app_dir() / "reels" / f"reel-{item.get('id', 0)}.json"
            spec.parent.mkdir(parents=True, exist_ok=True)
            spec.write_text(json.dumps({"title": item["name"], "items": item["reel"]}, ensure_ascii=False),
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
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self) -> None:
        assert self.proc and self.proc.stdout
        for raw in self.proc.stdout:
            line = raw.rstrip()
            if line:
                self._take(line)
        code = self.proc.wait()
        with self.lock:
            if self.state == "running":
                if code == 0 and self.result:
                    self.state, self.stage = "done", "done"
                else:
                    self.state = "error"
                    self.error = self.error or (self.lines[-1] if self.lines else f"Exit code {code}")
        if self.on_finish:
            self.on_finish()

    def _take(self, line: str) -> None:
        with self.lock:
            self.lines.append(line)
            if m := re.match(r"Starting CS2 .* record (\d+) clips", line):
                self.stage, self.step = "record", (0, int(m.group(1)))
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
            elif m := re.match(r"Cutting the reel (\d+)/(\d+)", line):
                self.stage, self.step = "cut", (int(m.group(1)), int(m.group(2)))
            elif line.startswith("Joining the reel"):
                self.stage, self.step = "cut", (1, 1)
            elif line.startswith("Done: "):
                self.result = line[6:].strip()
            elif line.startswith("Error: "):
                self.error = line[7:].strip()

    def cancel(self) -> None:
        from .. import hlae, settings_guard
        with self.lock:
            if self.state != "running" or not self.proc:
                return
            self.state = "cancelled"
        if sys.platform == "win32":
            # close the recording CS2 first, without letting it save settings
            subprocess.run(["taskkill", "/im", "cs2.exe", "/f"], capture_output=True)
            subprocess.run(["taskkill", "/pid", str(self.proc.pid), "/t", "/f"], capture_output=True)
        else:
            self.proc.terminate()
        for _ in range(20):
            if "cs2.exe" not in hlae.running_processes():
                break
            time.sleep(0.5)
        try:
            settings_guard.restore()
        except Exception:
            pass


class Queue:
    """Recordings waiting their turn; runs them one after another through Job."""

    def __init__(self, job: Job, prefs: dict):
        self.job, self.prefs = job, prefs
        self.lock = threading.Lock()
        self.items: list[dict] = []
        self.next_id = 1
        self.paused = False
        job.on_finish = self._finished

    def snapshot(self) -> dict:
        with self.lock:
            return {"items": [dict(i) for i in self.items], "paused": self.paused}

    def add(self, path: str, steamid: str, name: str, rounds: list[int], map_pretty: str) -> dict:
        return self._add({"kind": "match", "path": path, "steamid": steamid, "name": name, "rounds": rounds,
                          "map": map_pretty})

    def add_reel(self, title: str, items: list[dict], summary: str = "") -> dict:
        """A highlight reel: items are {demo, steamid, round} in the order they appear."""
        reel = [{"demo": str(i["demo"]), "steamid": str(i["steamid"]), "round": int(i["round"])} for i in items]
        if not reel:
            raise ValueError("No rounds in the reel.")
        return self._add({"kind": "reel", "name": title or "Highlights", "reel": reel, "rounds": [],
                          "path": "", "steamid": "", "map": summary})

    def _add(self, fields: dict) -> dict:
        with self.lock:
            item = {"id": self.next_id, **fields, "state": "queued", "result": "", "highlights": "",
                    "cover": "", "description": "", "title": "", "error": ""}
            self.next_id += 1
            self.items.append(item)
            self.paused = False
        self._start_next()
        return item

    def _start_next(self) -> None:
        with self.lock:
            if self.paused or self.job.state == "running":
                return
            item = next((i for i in self.items if i["state"] == "queued"), None)
            if item is None:
                return
            item["state"] = "running"
        try:
            self.job.start(dict(item), self.prefs)
        except Exception as e:
            with self.lock:
                item["state"], item["error"] = "error", str(e)

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
        self._start_next()

    def resume(self) -> None:
        with self.lock:
            self.paused = False
        self._start_next()

    def retry(self, item_id: int) -> None:
        with self.lock:
            for i in self.items:
                if i["id"] == item_id and i["state"] in ("error", "cancelled"):
                    i["state"], i["error"] = "queued", ""
            self.paused = False
        self._start_next()

    def remove(self, item_id: int) -> None:
        with self.lock:
            self.items = [i for i in self.items if i["id"] != item_id or i["state"] == "running"]

    def clear_finished(self) -> None:
        with self.lock:
            self.items = [i for i in self.items if i["state"] in ("queued", "running")]


# --- updates -----------------------------------------------------------------------------

RELEASES_API = "https://api.github.com/repos/Chester-chs/CS2-povforge/releases/latest"
RELEASES_PAGE = "https://github.com/Chester-chs/CS2-povforge/releases/latest"


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


DOWNLOADS = "https://github.com/Chester-chs/CS2-povforge/releases/download/"
SETUP_ASSET = "PovForge-Setup.exe"


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
                "setup": f"{DOWNLOADS}{tag}/{SETUP_ASSET}", "size": 0, "sha256": ""}
    if not info["setup"].startswith(DOWNLOADS):
        info["setup"] = ""        # only ever download our own release assets
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
                "fraction": self.fraction, "done_mb": self.done_mb,
                "can_install": can_self_update() or bool(os.environ.get("POVFORGE_PLACEHOLDER"))}

    def install(self) -> dict:
        with self.lock:
            if self.state != "available" or not self.info or not self.info.get("setup"):
                return self.status_unlocked()
            if self.busy():
                self.error = "busy"
                return self.status_unlocked()
            self.state, self.error, self.fraction, self.done_mb = "downloading", "", 0.0, 0
        threading.Thread(target=self._work, daemon=True).start()
        return self.status()

    def _work(self) -> None:
        import hashlib
        import tempfile
        import urllib.request
        info = self.info or {}
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
        if select:
            subprocess.Popen(["explorer", "/select,", str(p)])
        else:
            os.startfile(str(p))  # noqa: S606 - opens with the user's default app
    else:
        subprocess.Popen(["xdg-open", str(p.parent if select else p)])


def pick_file(initial: str) -> str | None:
    """Native file dialog (tkinter); runs on its own thread so the server keeps going."""
    result: list[str | None] = [None]

    def ask() -> None:
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            result[0] = filedialog.askopenfilename(
                title="CS2 demo", initialdir=initial,
                filetypes=[("CS2 demo", "*.dem *.zst *.gz *.bz2"), ("All files", "*.*")]) or None
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
        self.prefs = load_prefs()
        self.job = Job()
        self.queue = Queue(self.job, self.prefs)
        self.setup = Setup()
        self.update: dict | None = None
        self.quit = lambda: None            # set by main() once the server exists
        self.updater = Updater(__version__, busy=lambda: self.job.state == "running",
                               quit_app=lambda: self.quit())
        threading.Thread(target=self._check_update, daemon=True).start()

    def _check_update(self) -> None:
        self.update = check_update(__version__)
        self.last_seen = time.time()   # the page asks for state every second or two


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
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

        def _same_origin(self) -> bool:
            # only the app page may call the API (blocks other sites in the browser)
            origin = self.headers.get("Origin")
            host = self.headers.get("Host", "")
            return origin is None or origin == f"http://{host}"

        def do_GET(self) -> None:
            url = urlparse(self.path)
            q = parse_qs(url.query)
            try:
                if url.path == "/":
                    return self._file(STATIC / "index.html")
                if url.path.startswith("/static/"):
                    f = (STATIC / url.path[len("/static/"):]).resolve()
                    if STATIC.resolve() in f.parents and f.is_file():
                        return self._file(f)
                    return self._send(404, b"not found", "text/plain")
                if url.path.startswith("/api/"):
                    app.last_seen = time.time()
                if url.path == "/api/state":
                    return self._json({"version": __version__, "prefs": app.prefs, "update": app.update,
                                       "setup": app.setup.status(), "job": app.job.snapshot(),
                                       "queue": app.queue.snapshot()})
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
                if url.path == "/api/radar":
                    from ..maps import get_map
                    name = re.sub(r"[^a-z0-9_]", "", (q.get("map") or [""])[0].lower())
                    return self._file(get_map(name).radar)
                if url.path == "/api/thumb":
                    p = Path((q.get("path") or [""])[0])
                    if p.suffix.lower() in (".png", ".jpg") and p.is_file() and Path(app.prefs["output"]) in p.parents:
                        return self._file(p)
                    return self._send(404, b"not found", "text/plain")
                self._send(404, b"not found", "text/plain")
            except Exception as e:
                self._json({"error": str(e)}, 500)

        def do_POST(self) -> None:
            if not self._same_origin():
                return self._send(403, b"forbidden", "text/plain")
            url = urlparse(self.path)
            try:
                b = self._body()
                if url.path == "/api/inspect":
                    path = b.get("path", "")
                    if not is_demo(Path(path)):
                        return self._json({"error": "not_a_demo"}, 400)
                    return self._json(inspect_demo(path, Path(app.prefs["output"])))
                if url.path == "/api/browse":
                    folder = (app.prefs["demo_folders"] or [str(Path.home())])[0]
                    return self._json({"path": pick_file(folder)})
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
                if url.path == "/api/prefs":
                    for k in ("intro", "minimap", "keyboard", "show_enemies", "lang", "upload"):
                        if k in b:
                            app.prefs[k] = b[k]
                    if b.get("appearance") in ("auto", "light", "dark"):
                        app.prefs["appearance"] = b["appearance"]
                    if b.get("accent") in ACCENTS:
                        app.prefs["accent"] = b["accent"]
                    save_prefs(app.prefs)
                    return self._json(app.prefs)
                if url.path in ("/api/run", "/api/queue/add"):
                    app.queue.add(b["path"], b["steamid"], b.get("name", ""),
                                  [int(r) for r in b.get("rounds") or []], b.get("map", ""))
                    return self._json({**app.job.snapshot(), "queue": app.queue.snapshot()})
                if url.path == "/api/queue/add-reel":
                    app.queue.add_reel(b.get("title", ""), b.get("items") or [], b.get("summary", ""))
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
                    if app.job.state != "running":
                        app.job.reset()
                    return self._json(app.job.snapshot())
                if url.path == "/api/workfiles/clean":
                    if app.job.state == "running" or any(i["state"] in ("queued", "running") for i in app.queue.snapshot()["items"]):
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
                    from .. import settings_guard
                    settings_guard.restore()
                    return self._json(app.setup.status())
                if url.path == "/api/open":
                    p = b.get("path", "")
                    if not p or not Path(p).exists():
                        return self._json({"error": "missing"}, 404)
                    open_path(p, bool(b.get("select")))
                    return self._json({"ok": True})
                self._send(404, b"not found", "text/plain")
            except Exception as e:
                self._json({"error": str(e)}, 500)

        def _file(self, f: Path) -> None:
            self._send(200, Path(f).read_bytes(), CONTENT_TYPES.get(Path(f).suffix.lower(), "application/octet-stream"))

    return Handler


def open_window(url: str) -> None:
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
                subprocess.Popen([str(c), f"--app={url}", "--window-size=1280,820",
                                  f"--user-data-dir={profile}", "--no-first-run"])
                return
    for name in ("microsoft-edge", "google-chrome", "chromium"):
        exe = shutil.which(name)
        if exe:
            subprocess.Popen([exe, f"--app={url}", "--window-size=1280,820"])
            return
    webbrowser.open(url)


def main(port: int = 0, open_browser: bool = True) -> None:
    app = App()
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"PovForge is running at {url} (close this window to quit)", flush=True)
    if open_browser:
        open_window(url)
    app.quit = lambda: threading.Thread(target=server.shutdown, daemon=True).start()

    def watch() -> None:
        # quit once the window has been closed for a while (and nothing is recording)
        while True:
            time.sleep(5)
            if time.time() - app.last_seen > 30 and app.job.state != "running" and not app.setup.installing:
                server.shutdown()
                return

    threading.Thread(target=watch, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
