"""Read a CS2 demo with demoparser2 (https://github.com/LaihoE/demoparser).

This is the only module that talks to demoparser2; everything else works on
the plain data it returns, which keeps the rest of the code testable without
a demo file.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

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
    for folder in (path.parent, work_dir):
        if folder is None:
            continue
        out = folder / name
        if out.exists() and out.stat().st_size > 0:
            return out
        try:
            folder.mkdir(parents=True, exist_ok=True)
            tmp = out.with_suffix(".part")
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
            return out
        except OSError:
            continue
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
                ))

    return DemoData(path, map_name, tickrate, last_tick, players, rounds, deaths)


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
