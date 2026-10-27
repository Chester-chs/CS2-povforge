"""Automatic recording of downloaded official-matchmaking (Valve) demos.

The user downloads a match in CS2 (Watch -> Your Matches) and quits the game.
This watcher notices the new demo in CS2's ``replays`` folder, waits until the
file is complete and the user's own CS2 is closed, reads the demo, picks the
user's rounds and queues a normal recording. Recording itself starts CS2
through the usual queue, so the user never opens the game for it.

Only demos downloaded after the switch was turned on are handled. The user's
own running game is never closed: the watcher simply waits for it.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

MODES = ("kills", "kill_events", "kills_deaths", "match")
DEMO_SUFFIXES = (".dem", ".dem.bz2", ".dem.zst", ".dem.gz")
POLL_SECONDS = 4.0
SETTLE_SECONDS = 3.0           # a file unchanged this long (and across two polls) is complete
RECENT_LIMIT = 12
SEEN_LIMIT = 500
STEAMID = re.compile(r"7656\d{13}")

LABELS = {
    "zh": {"kills": "高光集锦", "kill_events": "击杀视角", "kills_deaths": "击杀和死亡视角", "match": "整场"},
    "en": {"kills": "Highlights", "kill_events": "Kill POV", "kills_deaths": "Kills & deaths POV", "match": "Whole match"},
}


# --- where things are ------------------------------------------------------------

def replays_folder(cs2_exe: Path | str | None) -> Path | None:
    """.../game/bin/win64/cs2.exe -> .../game/csgo/replays (where CS2 saves downloads)."""
    if not cs2_exe:
        return None
    return Path(cs2_exe).parents[2] / "csgo" / "replays"


def detect_replays_folder() -> Path | None:
    try:
        from . import hlae
        from .config import Config
        return replays_folder(hlae.find_cs2(Config().record))
    except Exception:
        return None


def steam_accounts(steam_dir: Path | str | None) -> list[dict]:
    """Steam accounts that signed in on this PC (config/loginusers.vdf), most recent first."""
    if not steam_dir:
        return []
    f = Path(steam_dir) / "config" / "loginusers.vdf"
    try:
        from .maps import parse_keyvalues
        kv = parse_keyvalues(f.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return []
    users = kv.get("users", kv)
    out = []
    if isinstance(users, dict):
        for sid, entry in users.items():
            if not STEAMID.fullmatch(str(sid)) or not isinstance(entry, dict):
                continue
            out.append({"steamid": str(sid), "name": str(entry.get("PersonaName") or entry.get("AccountName") or sid)[:64],
                        "recent": str(entry.get("MostRecent", "0")) == "1",
                        "at": int(entry.get("Timestamp", 0) or 0) if str(entry.get("Timestamp", "0")).isdigit() else 0})
    out.sort(key=lambda a: (not a["recent"], -a["at"]))
    return [{"steamid": a["steamid"], "name": a["name"], "recent": a["recent"]} for a in out]


def detect_accounts() -> list[dict]:
    try:
        from . import hlae
        return steam_accounts(hlae._steam_dir())
    except Exception:
        return []


# --- what to record --------------------------------------------------------------

def find_player(info: dict, steamid: str) -> dict | None:
    for team in info.get("teams") or []:
        for p in team.get("players") or []:
            if str(p.get("steamid")) == str(steamid):
                return p
    return None


def plan_rounds(player: dict, mode: str) -> list[int]:
    """The rounds a reel of ``mode`` uses, matching the editor's own choice."""
    kills = list(player.get("rounds_k") or [])
    events = list(player.get("rounds_event_k") or kills)
    died = list(player.get("rounds_died") or [])
    hs = list(player.get("rounds_hs") or [])
    clutch = list(player.get("rounds_clutch") or [])
    at = lambda xs, i: xs[i] if i < len(xs) and xs[i] else 0  # noqa: E731
    if mode == "kill_events":
        return [i + 1 for i in range(len(events)) if at(events, i) > 0]
    if mode == "kills_deaths":
        n = max(len(events), len(died))
        return [i + 1 for i in range(n) if at(events, i) > 0 or at(died, i)]
    # Highlights: 3+ kills or a won clutch, best moments last (as the editor orders them).
    score = lambda i: at(kills, i) * 10 + at(hs, i) + 25 * at(clutch, i)  # noqa: E731
    best = [i for i in range(len(kills)) if at(kills, i) >= 3 or at(clutch, i) >= 1]
    if not best:                              # a quiet match still gets its kills
        best = [i for i in range(len(kills)) if at(kills, i) > 0]
    return [i + 1 for i in sorted(best, key=lambda i: (score(i), i))]


def demo_stem(name: str) -> str:
    low = name.lower()
    for s in sorted(DEMO_SUFFIXES, key=len, reverse=True):
        if low.endswith(s):
            return name[: -len(s)]
    return name


# --- the watcher -----------------------------------------------------------------

class Watcher:
    """Polls the replays folder in a background thread. Dependencies are injected
    so the decisions can be tested without Windows, Steam or CS2."""

    def __init__(self, prefs: dict, state_dir: Path, *, inspect, queue, game_busy,
                 save_prefs=lambda prefs: None, folder_finder=detect_replays_folder,
                 accounts_finder=detect_accounts, clock=time.time):
        self.prefs = prefs
        self.store = Path(state_dir) / "auto-demos.json"
        self.inspect = inspect              # path -> demo info (as the app's inspection)
        self.queue = queue                  # the app's Queue
        self.game_busy = game_busy          # -> "" when free, else "cs2" | "anticheat"
        self.save_prefs = save_prefs
        self.folder_finder = folder_finder
        self.accounts_finder = accounts_finder
        self.clock = clock
        self.lock = threading.Lock()
        self.sizes: dict[str, tuple[int, int]] = {}
        self.waiting = ""                   # why found demos are not being read yet
        self.working = ""                   # demo being read now
        self._detected: Path | None = None
        self._looked = False
        self._accounts: list[dict] | None = None
        self.seen = self._load()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # persistence
    def _load(self) -> dict:
        try:
            data = json.loads(self.store.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self) -> None:
        rows = sorted(self.seen.items(), key=lambda kv: -float(kv[1].get("at", 0)))[:SEEN_LIMIT]
        self.seen = dict(rows)
        try:
            self.store.parent.mkdir(parents=True, exist_ok=True)
            temp = self.store.with_name(f"auto-demos.{secrets.token_hex(6)}.tmp")
            temp.write_text(json.dumps(self.seen, ensure_ascii=False), encoding="utf-8")
            temp.replace(self.store)
        except OSError:
            pass

    # settings
    def folder(self) -> Path | None:
        custom = self.prefs.get("auto_mm_folder")
        if custom:
            return Path(custom)
        if not self._looked:
            self._detected, self._looked = self.folder_finder(), True
        return self._detected

    def accounts(self, refresh: bool = False) -> list[dict]:
        if self._accounts is None or refresh:
            self._accounts = self.accounts_finder()
            if refresh:
                self._looked = False          # CS2 may have been installed or moved meanwhile
        return self._accounts

    def account(self) -> dict | None:
        chosen = self.prefs.get("auto_mm_steamid") or ""
        accounts = self.accounts()
        if chosen:
            return next((a for a in accounts if a["steamid"] == chosen), {"steamid": chosen, "name": ""})
        return accounts[0] if accounts else None

    def configure(self, values: dict) -> None:
        with self.lock:
            if "mode" in values and values["mode"] in MODES:
                self.prefs["auto_mm_mode"] = values["mode"]
            if "steamid" in values:
                sid = str(values["steamid"] or "")
                if sid and not STEAMID.fullmatch(sid):
                    raise ValueError("invalid account")
                self.prefs["auto_mm_steamid"] = sid
            if "folder" in values:
                folder = values["folder"]
                if folder:
                    p = Path(folder)
                    if not p.is_absolute() or not p.is_dir():
                        raise ValueError("invalid folder")
                    self.prefs["auto_mm_folder"] = str(p)
                else:
                    self.prefs.pop("auto_mm_folder", None)
                self.sizes.clear()
            if "enabled" in values:
                on = bool(values["enabled"])
                if on and not self.prefs.get("auto_mm"):
                    # Only demos that arrive from now on; never the user's backlog.
                    self.prefs["auto_mm_since"] = self.clock()
                self.prefs["auto_mm"] = on
                self.sizes.clear()
            self.prefs.setdefault("auto_mm_mode", "kills")
            self.save_prefs(self.prefs)

    def status(self) -> dict:
        folder = self.folder()
        acc = self.account()
        with self.lock:
            recent = sorted((dict(v, key=k) for k, v in self.seen.items() if v.get("state") != "existing"),
                            key=lambda r: -float(r.get("at", 0)))[:RECENT_LIMIT]
            return {"enabled": bool(self.prefs.get("auto_mm")), "mode": self.prefs.get("auto_mm_mode", "kills"),
                    "folder": str(folder) if folder else "", "folder_found": bool(folder and folder.is_dir()),
                    "custom_folder": bool(self.prefs.get("auto_mm_folder")),
                    "accounts": self.accounts(), "steamid": (acc or {}).get("steamid", ""),
                    "account_name": (acc or {}).get("name", ""),
                    "waiting": self.waiting, "working": self.working,
                    "recent": [{k: r.get(k, "") for k in ("name", "state", "message", "at", "title")} for r in recent]}

    # the loop
    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def close(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(POLL_SECONDS):
            try:
                self.tick()
            except Exception as e:           # never let one bad file stop the watching
                print(f"Auto recording: {e}", flush=True)

    def candidates(self) -> list[Path]:
        """New, complete demos in the folder, oldest first (one per match)."""
        folder = self.folder()
        if not self.prefs.get("auto_mm") or not folder or not folder.is_dir():
            return []
        since = float(self.prefs.get("auto_mm_since") or 0)
        now = self.clock()
        groups: dict[str, list[tuple[Path, bool, float]]] = {}
        current: dict[str, tuple[int, int]] = {}
        try:
            entries = list(folder.iterdir())[:5000]
        except OSError:
            return []
        for p in entries:
            if not p.name.lower().endswith(DEMO_SUFFIXES) or p.is_symlink():
                continue
            try:
                st = p.stat()
                if not p.is_file():
                    continue
            except OSError:
                continue
            if st.st_mtime < since or st.st_size <= 0:
                continue
            sig = (st.st_size, st.st_mtime_ns)
            current[str(p)] = sig
            stem = demo_stem(p.name).lower()
            if self._seen_key(folder, stem) in self.seen:
                continue
            stable = self.sizes.get(str(p)) == sig and now - st.st_mtime >= SETTLE_SECONDS
            groups.setdefault(stem, []).append((p, stable, st.st_mtime))
        self.sizes = current
        ready = []
        for files in groups.values():
            if not all(stable for _, stable, _ in files):
                continue                     # part of this match is still being written
            # An unpacked .dem is preferred over its archive.
            files.sort(key=lambda f: (not f[0].name.lower().endswith(".dem"), f[0].name))
            ready.append((files[0][2], files[0][0]))
        return [p for _, p in sorted(ready, key=lambda r: (r[0], r[1].name))]

    @staticmethod
    def _seen_key(folder: Path, stem: str) -> str:
        return os.path.normcase(str(folder)) + "|" + stem

    def _mark(self, folder: Path, path: Path, state: str, message: str = "", title: str = "") -> None:
        with self.lock:
            self.seen[self._seen_key(folder, demo_stem(path.name).lower())] = {
                "name": path.name, "state": state, "message": message, "title": title, "at": self.clock()}
            self._save()

    def tick(self) -> None:
        ready = self.candidates()
        if not ready:
            self.waiting = ""
            return
        busy = self.game_busy()
        self.waiting = busy
        if busy:
            return                           # wait for the user's own game to close
        folder = self.folder()
        for path in ready:
            if self._stop.is_set() or not self.prefs.get("auto_mm"):
                return
            busy = self.game_busy()          # the user may have reopened the game meanwhile
            if busy:
                self.waiting = busy
                return
            self.process(folder, path)

    def process(self, folder: Path, path: Path) -> None:
        lang = "en" if self.prefs.get("lang") == "en" else "zh"
        zh = lang == "zh"
        acc = self.account()
        if not acc:
            self._mark(folder, path, "skipped", "未找到本机登录过的 Steam 账号，请在设置中选择要录制的账号。" if zh
                       else "No Steam account found on this PC. Choose the account in Settings.")
            return
        self.working = path.name
        try:
            info = self.inspect(str(path))
        except Exception as e:
            self._mark(folder, path, "error", ("读取 demo 失败：" if zh else "Could not read the demo: ") + str(e)[:300])
            return
        finally:
            self.working = ""
        player = find_player(info, acc["steamid"])
        if player is None:
            self._mark(folder, path, "skipped", "这场比赛里没有找到你的账号，已跳过。" if zh
                       else "Your account is not in this match; skipped.")
            return
        mode = self.prefs.get("auto_mm_mode", "kills")
        mode = mode if mode in MODES else "kills"
        name = str(player.get("name") or acc.get("name") or acc["steamid"])
        map_pretty = str(info.get("map_pretty") or info.get("map") or "")
        label = LABELS[lang][mode]
        title = (f"{name} 官匹{label}" if zh else f"{name} matchmaking {label}") + (f" · {map_pretty}" if map_pretty else "")
        if mode == "match":
            self.queue.add(str(path), acc["steamid"], name, [], map_pretty)
            self._mark(folder, path, "queued", "已加入录制队列。" if zh else "Added to the recording queue.", title)
            return
        rounds = plan_rounds(player, mode)
        if not rounds:
            self._mark(folder, path, "skipped", "这场比赛没有可剪辑的击杀回合，已跳过。" if zh
                       else "No rounds with kills to cut; skipped.", title)
            return
        items = [{"demo": str(path), "steamid": acc["steamid"], "round": r, "name": name,
                  "mode": mode, "opponent": "", "weapons": []} for r in rounds]
        from . import effects
        saved = effects.normalize(self.prefs.get("reel_fx"))
        # Event reels keep only audio/camera choices, like the editor does.
        fx = saved if mode == "kills" else {**effects.normalize(None),
                                             **{k: saved[k] for k in ("camera", "music", "music_volume",
                                                                      "music_start", "music_sync", "game_audio")}}
        if fx.get("music") and not Path(fx["music"]).is_file():
            # Unattended: record without the vanished track rather than failing the match.
            fx = {**fx, "music": "", "music_sync": False}
        summary = f"{map_pretty}  " + (f"{len(rounds)} 个回合" if zh else f"{len(rounds)} rounds")
        self.queue.add_reel(title, items, summary.strip(), fx)
        self._mark(folder, path, "queued", ("已加入录制队列：" if zh else "Queued: ") +
                   (f"{len(rounds)} 个回合。" if zh else f"{len(rounds)} rounds."), title)
