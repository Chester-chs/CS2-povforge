"""Read a CS2 demo with demoparser2 (https://github.com/LaihoE/demoparser).

This is the only module that talks to demoparser2; everything else works on
the plain data it returns, which keeps the rest of the code testable without
a demo file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import os
import tempfile

import numpy as np
import pandas as pd

from .model import Death, Player, Round
from .planner import build_rounds

DEFAULT_TICKRATE = 64.0

# Per-player fields needed for the minimap.
POSITION_FIELDS = ["X", "Y", "Z", "yaw", "is_alive", "team_num"]

# Keyboard overlay keys and their bits in CS2's input button mask
# (IN_ATTACK = 1 << 0, IN_JUMP = 1 << 1, ...).
BUTTON_BITS = {
    "FORWARD": 1 << 3, "BACK": 1 << 4, "LEFT": 1 << 9, "RIGHT": 1 << 10,  # W S A D
    "JUMP": 1 << 1, "DUCK": 1 << 2, "WALK": 1 << 16,                     # Space Ctrl Shift
    "FIRE": 1 << 0, "RIGHTCLICK": 1 << 11,                                # mouse
    "RELOAD": 1 << 13, "USE": 1 << 5,                                     # R E
}
BUTTON_FIELDS = list(BUTTON_BITS)

# Where the button mask can come from, best first:
#  * usercmd_buttonstate_1: the player's real input commands, recorded in
#    newer CS2 demos (FACEIT demos have them);
#  * buttons: the server-side copy of the button mask (one tick behind).
_MASK_SOURCES = ["usercmd_buttonstate_1", "buttons"]


@dataclass
class DemoData:
    path: Path
    map_name: str
    tickrate: float
    last_tick: int
    players: list[Player]
    rounds: list[Round]
    deaths: list[Death]
    winners: dict[int, int] = field(default_factory=dict)  # round_end tick -> 2 (T) / 3 (CT)
    round_starts: list[int] = field(default_factory=list)


def event_round_end(demo, round_: Round) -> int:
    """Exclusive event boundary: exit frags belong to the round just played."""
    next_freeze = min((r.freeze_end_tick for r in demo.rounds if r.freeze_end_tick > round_.freeze_end_tick), default=None)
    starts = [t for t in getattr(demo, "round_starts", [])
              if t > round_.freeze_end_tick and (next_freeze is None or t <= next_freeze)]
    if starts:
        return min(starts)
    if next_freeze is None:
        return getattr(demo, "last_tick", round_.end_tick + 1)
    # In old/malformed demos without round_start, retain the normal two-second tail.
    return min(next_freeze, round_.end_tick + max(1, round(2 * demo.tickrate)))


def _sid(v) -> str | None:
    """Normalise a steamid from demoparser2 (int, float or str) to a string."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).split(".")[0].strip()
    return s if s and s not in ("0", "nan", "None") else None


def prepare_demo(path: str | Path, work_dir: Path | None = None) -> Path:
    """Accept .dem, or compressed .dem.zst (FACEIT) / .dem.gz / .dem.bz2.

    Compressed demos are unpacked once, next to the original (or into
    ``work_dir`` if that folder isn't writable); later runs reuse the file.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in (".zst", ".gz", ".bz2"):
        return path
    name = path.name[: -len(suffix)]
    if not name.lower().endswith(".dem"):
        name += ".dem"
    stat = path.stat()
    source = {"path": str(path.resolve()), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    for folder in (path.parent, work_dir):
        if folder is None:
            continue
        out = folder / name
        provenance = out.with_name(out.name + ".source.json")
        try:
            saved = json.loads(provenance.read_text(encoding="utf-8"))
            stat = out.stat()
            if (saved["source"] == source and stat.st_size > 0
                    and saved["output"] == [stat.st_size, stat.st_mtime_ns]):
                return out
        except (OSError, ValueError, KeyError, TypeError):
            pass
        tmp = metadata_tmp = None
        try:
            folder.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(dir=folder, prefix=out.name + ".", suffix=".part")
            os.close(fd)
            tmp = Path(temporary)
            with open(path, "rb") as src, open(tmp, "wb") as dst:
                if suffix == ".zst":
                    import zstandard
                    zstandard.ZstdDecompressor().copy_stream(src, dst)
                else:
                    import bz2
                    import gzip
                    import shutil
                    opener = gzip.open if suffix == ".gz" else bz2.open
                    with opener(src) as z:
                        shutil.copyfileobj(z, dst, 1 << 20)
            tmp.replace(out)
            stat = out.stat()
            metadata_tmp = tmp.with_suffix(".json")
            metadata_tmp.write_text(json.dumps({"source": source,
                                                "output": [stat.st_size, stat.st_mtime_ns]}), encoding="utf-8")
            metadata_tmp.replace(provenance)
            return out
        except OSError:
            continue
        finally:
            if tmp is not None:
                tmp.unlink(missing_ok=True)
            if metadata_tmp is not None:
                metadata_tmp.unlink(missing_ok=True)
    raise RuntimeError(f"Could not unpack {path}")


def _parser(path: Path):
    try:
        from demoparser2 import DemoParser
    except ImportError as e:  # pragma: no cover - depends on the environment
        raise SystemExit(
            "demoparser2 is not installed. Run: pip install demoparser2"
        ) from e
    return DemoParser(str(path))


def _event_ticks(parser, name: str) -> list[int]:
    try:
        df = parser.parse_event(name)
    except Exception:
        return []
    if df is None or len(df) == 0 or "tick" not in df:
        return []
    return [int(t) for t in df["tick"].tolist()]


def load_demo(path: str | Path, tickrate: float = DEFAULT_TICKRATE) -> DemoData:
    path = Path(path)
    parser = _parser(path)

    header = parser.parse_header() or {}
    map_name = str(header.get("map_name", "unknown"))

    info = parser.parse_player_info()
    players = []
    seen = set()
    for _, row in info.iterrows():
        sid = _sid(row.get("steamid"))
        if sid and sid not in seen:
            seen.add(sid)
            players.append(Player(steamid=sid, name=str(row.get("name", ""))))

    # Last tick: cheap query of a single field over the whole demo.
    t = parser.parse_ticks(["is_alive"])
    last_tick = int(t["tick"].max()) if len(t) else 0

    match_start = max(
        _event_ticks(parser, "round_announce_match_start")
        + _event_ticks(parser, "begin_new_match")
        + [0]
    )
    rounds = build_rounds(
        _event_ticks(parser, "round_freeze_end"),
        _event_ticks(parser, "round_end"),
        match_start,
        last_tick,
    )

    deaths: list[Death] = []
    try:
        dd = parser.parse_event("player_death")
    except Exception:
        dd = None
    if dd is not None and len(dd):
        for _, row in dd.iterrows():
            victim = _sid(row.get("user_steamid"))
            if victim:
                deaths.append(Death(
                    tick=int(row["tick"]),
                    victim_steamid=victim,
                    attacker_steamid=_sid(row.get("attacker_steamid")),
                    weapon=row.get("weapon"),
                    headshot=bool(row.get("headshot") or False),
                ))

    winners: dict[int, int] = {}
    try:
        re_ = parser.parse_event("round_end")
        for _, row in re_.iterrows():
            w = str(row.get("winner") or "").upper()
            if w in ("T", "CT", "2", "3"):
                winners[int(row["tick"])] = 2 if w in ("T", "2") else 3
    except Exception:
        pass

    return DemoData(path, map_name, tickrate, last_tick, players, rounds, deaths, winners,
                    _event_ticks(parser, "round_start"))


MIN_PRESS_TICKS = 4  # show even the shortest tap for ~60 ms so it's visible


def _mask(col: pd.Series) -> np.ndarray:
    return pd.to_numeric(col, errors="coerce").fillna(0).astype("uint64").to_numpy()


def _stretch(on: np.ndarray, n: int) -> np.ndarray:
    """Keep every press visible for at least ``n`` consecutive rows."""
    out = on.copy()
    starts = np.flatnonzero(on & ~np.concatenate([[False], on[:-1]]))
    for s in starts:
        out[s:s + n] = True
    return out


def decode_buttons(held: np.ndarray, changed: np.ndarray | None = None,
                   min_ticks: int = MIN_PRESS_TICKS) -> dict[str, np.ndarray]:
    """Turn button masks into one boolean array per overlay key.

    ``held`` is the mask of buttons down at the end of each tick. ``changed``
    (when the demo has it) marks buttons that changed during the tick; a
    button that changed but is neither down now nor was down before was
    tapped within a single tick (sub-tick input), which ``held`` alone misses.
    """
    held = held.astype("uint64")
    shown = held
    if changed is not None:
        prev = np.concatenate([[0], held[:-1]]).astype("uint64")
        shown = held | (changed.astype("uint64") & ~held & ~prev)
    return {k: _stretch((shown & np.uint64(bit)) != 0, min_ticks) for k, bit in BUTTON_BITS.items()}


def load_ticks(path: str | Path, target_steamid: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (positions of all players, key states of the target player).

    The key table is empty when the demo carries no input data.
    """
    parser = _parser(Path(path))
    pos = parser.parse_ticks(POSITION_FIELDS)
    pos["steamid"] = pos["steamid"].map(_sid)

    keys = pd.DataFrame(columns=["tick", *BUTTON_FIELDS])
    for source in _MASK_SOURCES:
        wanted = [source] + (["usercmd_buttonstate_2"] if source.startswith("usercmd") else [])
        try:
            raw = parser.parse_ticks(wanted, players=[int(target_steamid)])
        except Exception:
            continue
        if source not in raw or raw[source].isna().all():
            continue
        raw = raw[raw["steamid"].map(_sid) == target_steamid].sort_values("tick")
        changed = _mask(raw["usercmd_buttonstate_2"]) if "usercmd_buttonstate_2" in raw else None
        cols = decode_buttons(_mask(raw[source]), changed)
        keys = pd.DataFrame({"tick": raw["tick"].to_numpy(), **cols})
        keys.attrs["source"] = source
        break
    return pos, keys


# What the player's own HUD shows, sampled every tick for the followed player.
HUD_FIELDS = ["health", "armor_value", "has_helmet", "balance", "active_weapon_name",
              "active_weapon_ammo", "total_ammo_left", "is_alive", "is_scoped", "last_place_name"]


def load_hud(path: str | Path, target_steamid: str) -> pd.DataFrame:
    parser = _parser(Path(path))
    try:
        df = parser.parse_ticks(HUD_FIELDS, players=[int(target_steamid)])
    except Exception:
        return pd.DataFrame(columns=["tick", *HUD_FIELDS])
    df = df[df["steamid"].map(_sid) == target_steamid]
    keep = ["tick"] + [c for c in HUD_FIELDS if c in df]
    return df[keep].sort_values("tick").reset_index(drop=True)


# Thrown grenades, for the minimap.
PROJECTILE_KIND = {
    "CSmokeGrenadeProjectile": "smoke", "CFlashbangProjectile": "flash",
    "CHEGrenadeProjectile": "he", "CMolotovProjectile": "fire",
    "CIncendiaryGrenadeProjectile": "fire", "CDecoyProjectile": "decoy",
}


def load_utility(path: str | Path) -> dict[str, pd.DataFrame]:
    """Grenade flight paths and what they leave behind (smokes, fires, bursts).

    Returns DataFrames: 'paths' (entity, kind, tick, x, y, steamid),
    'smokes' / 'fires' (start, end, x, y, steamid), 'bursts' (tick, x, y, kind).
    """
    parser = _parser(Path(path))
    out: dict[str, pd.DataFrame] = {}
    try:
        g = parser.parse_grenades()
        g = g[g["grenade_type"].isin(PROJECTILE_KIND)].dropna(subset=["x", "y"])
        out["paths"] = pd.DataFrame({
            "entity": g["grenade_entity_id"].astype(int), "kind": g["grenade_type"].map(PROJECTILE_KIND),
            "tick": g["tick"].astype(int), "x": g["x"].astype(float), "y": g["y"].astype(float),
            "steamid": g["steamid"].map(_sid),
        }).sort_values(["entity", "tick"]).reset_index(drop=True)
    except Exception:
        out["paths"] = pd.DataFrame(columns=["entity", "kind", "tick", "x", "y", "steamid"])

    def events(name: str) -> pd.DataFrame:
        try:
            d = parser.parse_event(name)
        except Exception:
            return pd.DataFrame(columns=["entityid", "tick", "x", "y", "user_steamid"])
        return d if isinstance(d, pd.DataFrame) and len(d) else \
            pd.DataFrame(columns=["entityid", "tick", "x", "y", "user_steamid"])

    def spans(start_ev: str, end_ev: str, default_len: int) -> pd.DataFrame:
        a, b = events(start_ev), events(end_ev)
        ends = {}
        for _, r in b.sort_values("tick").iterrows():
            ends.setdefault(int(r["entityid"]), []).append(int(r["tick"]))
        rows = []
        for _, r in a.sort_values("tick").iterrows():
            t0 = int(r["tick"])
            later = [t for t in ends.get(int(r["entityid"]), []) if t > t0]
            rows.append({"start": t0, "end": later[0] if later else t0 + default_len,
                         "x": float(r["x"]), "y": float(r["y"]), "steamid": _sid(r.get("user_steamid"))})
        return pd.DataFrame(rows, columns=["start", "end", "x", "y", "steamid"])

    out["smokes"] = spans("smokegrenade_detonate", "smokegrenade_expired", 20 * 64)
    out["fires"] = spans("inferno_startburn", "inferno_expire", 7 * 64)
    bursts = []
    for ev, kind in (("flashbang_detonate", "flash"), ("hegrenade_detonate", "he")):
        for _, r in events(ev).iterrows():
            bursts.append({"tick": int(r["tick"]), "x": float(r["x"]), "y": float(r["y"]), "kind": kind})
    out["bursts"] = pd.DataFrame(bursts, columns=["tick", "x", "y", "kind"])
    return out


@dataclass
class PlayerStats:
    steamid: str
    name: str
    kills: int
    deaths: int
    assists: int
    adr: float
    hs_pct: float
    mvps: int


@dataclass
class TeamStats:
    name: str
    score: int
    players: list[PlayerStats]


SCOREBOARD_FIELDS = ["team_num", "team_rounds_total", "team_clan_name", "kills_total", "deaths_total",
                     "assists_total", "damage_total", "headshot_kills_total", "mvps"]


def load_scoreboard(path: str | Path, rounds_played: int) -> list[TeamStats]:
    """Final scoreboard (as shown in game) from the last tick of the demo."""
    parser = _parser(Path(path))
    last = int(parser.parse_ticks(["is_alive"])["tick"].max())
    df = None
    for t in range(last, max(0, last - 640), -64):  # some demos end with empty ticks
        d = parser.parse_ticks(SCOREBOARD_FIELDS, ticks=[t])
        if len(d) and d["team_num"].isin([2, 3]).any():
            df = d
            break
    if df is None:
        return []
    rounds = max(1, rounds_played)
    teams: list[TeamStats] = []
    for team_num in (2, 3):
        rows = df[df["team_num"] == team_num]
        if not len(rows):
            continue
        players = []
        for _, r in rows.iterrows():
            kills = int(r.get("kills_total") or 0)
            players.append(PlayerStats(
                steamid=_sid(r["steamid"]) or "", name=str(r["name"]),
                kills=kills, deaths=int(r.get("deaths_total") or 0),
                assists=int(r.get("assists_total") or 0),
                adr=float(r.get("damage_total") or 0) / rounds,
                hs_pct=100.0 * int(r.get("headshot_kills_total") or 0) / kills if kills else 0.0,
                mvps=int(r.get("mvps") or 0),
            ))
        players.sort(key=lambda p: (-p.kills, p.deaths))
        name = str(rows["team_clan_name"].iloc[0] or "") if "team_clan_name" in rows else ""
        teams.append(TeamStats(name or ("T" if team_num == 2 else "CT"),
                               int(rows["team_rounds_total"].iloc[0] or 0), players))
    return teams


def round_sides(path: str | Path, rounds: list[Round]) -> dict[int, dict[str, int]]:
    """For each round: {steamid: team (2 = T, 3 = CT)} of the players alive when
    freeze time ends. Reads only those few ticks, so it's quick."""
    if not rounds:
        return {}
    parser = _parser(Path(path))
    ticks = [r.freeze_end_tick + 1 for r in rounds]
    df = parser.parse_ticks(["team_num", "is_alive"], ticks=ticks)
    by_tick: dict[int, dict[str, int]] = {}
    for _, row in df.iterrows():
        sid = _sid(row.get("steamid"))
        team = int(row.get("team_num") or 0)
        if sid and team in (2, 3) and bool(row.get("is_alive")):
            by_tick.setdefault(int(row["tick"]), {})[sid] = team
    return {r.number: by_tick.get(t, {}) for r, t in zip(rounds, ticks)}


def find_player(players: list[Player], query: str) -> Player:
    """Match by steamid, exact name, or a unique case-insensitive substring."""
    q = query.strip()
    for p in players:
        if p.steamid == q:
            return p
    exact = [p for p in players if p.name.lower() == q.lower()]
    if len(exact) == 1:
        return exact[0]
    partial = [p for p in players if q.lower() in p.name.lower()]
    if len(partial) == 1:
        return partial[0]
    names = ", ".join(f"{p.name} ({p.steamid})" for p in players)
    if not partial:
        raise ValueError(f"No player matches '{query}'. Players in this demo: {names}")
    raise ValueError(
        f"'{query}' matches several players: "
        + ", ".join(p.name for p in partial)
        + ". Use the full name or steamid."
    )
