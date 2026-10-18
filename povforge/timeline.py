"""Map video frames to demo ticks and sample player state at any tick.

The recorder renders offline at a fixed frame rate, so frame ``i`` of a clip
that starts at ``start_tick`` shows game time ``start_tick + i * tickrate / fps``.
That makes overlay sync a pure calculation; ``offset_frames`` exists only to
correct a constant shift if a real recording shows one.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .demo import BUTTON_FIELDS


def frame_count(start_tick: int, end_tick: int, tickrate: float, fps: float) -> int:
    return max(1, int(round((end_tick - start_tick) / tickrate * fps)))


def frame_to_tick(i: int, start_tick: int, tickrate: float, fps: float,
                  offset_frames: float = 0.0) -> float:
    return start_tick + (i + offset_frames) * tickrate / fps


@dataclass
class PlayerState:
    steamid: str
    x: float
    y: float
    z: float
    yaw: float
    alive: bool
    team: int


class _Series:
    def __init__(self, df: pd.DataFrame):
        df = df.sort_values("tick").drop_duplicates("tick", keep="last")
        self.ticks = df["tick"].to_numpy(dtype=np.float64)
        self.x = df["X"].to_numpy(dtype=np.float64)
        self.y = df["Y"].to_numpy(dtype=np.float64)
        self.z = df["Z"].to_numpy(dtype=np.float64)
        self.yaw = df["yaw"].to_numpy(dtype=np.float64)
        self.alive = df["is_alive"].fillna(False).to_numpy(dtype=bool)
        self.team = df["team_num"].fillna(0).to_numpy(dtype=np.int64)

    def at(self, tick: float):
        n = len(self.ticks)
        if n == 0 or tick < self.ticks[0]:
            return None
        j = int(np.searchsorted(self.ticks, tick, side="right")) - 1
        if j >= n - 1:
            j = n - 1
            return self.x[j], self.y[j], self.z[j], self.yaw[j], self.alive[j], self.team[j]
        t0, t1 = self.ticks[j], self.ticks[j + 1]
        a = (tick - t0) / (t1 - t0) if t1 > t0 else 0.0
        if not (self.alive[j] and self.alive[j + 1]):
            a = 0.0  # don't slide a dead player across the map
        x = self.x[j] + (self.x[j + 1] - self.x[j]) * a
        y = self.y[j] + (self.y[j + 1] - self.y[j]) * a
        z = self.z[j] + (self.z[j + 1] - self.z[j]) * a
        dyaw = (self.yaw[j + 1] - self.yaw[j] + 180.0) % 360.0 - 180.0
        yaw = self.yaw[j] + dyaw * a
        return x, y, z, yaw, bool(self.alive[j]), int(self.team[j])


@dataclass
class HudState:
    alive: bool = False
    health: int = 0
    armor: int = 0
    helmet: bool = False
    money: int = 0
    weapon: str = ""
    ammo: int = -1          # -1 = weapon without a magazine (knife, grenade)
    reserve: int = -1       # -1 = unknown (CS2 demos don't carry reliable reserve ammo)
    scoped: bool = False
    place: str = ""


class Track:
    """Fast per-tick lookups over the parsed position and button tables."""

    def __init__(self, positions: pd.DataFrame, buttons: pd.DataFrame | None = None,
                 hud: pd.DataFrame | None = None, utility: dict | None = None):
        self.utility = Utility(utility)
        self._hud_ticks = np.empty(0)
        self._hud: pd.DataFrame | None = None
        if hud is not None and len(hud):
            h = hud.sort_values("tick").drop_duplicates("tick", keep="last").reset_index(drop=True)
            self._hud_ticks = h["tick"].to_numpy(dtype=np.float64)
            self._hud = h
        self._players = {
            sid: _Series(g) for sid, g in positions.groupby("steamid") if sid
        }
        self._key_ticks = np.empty(0)
        self._keys: dict[str, np.ndarray] = {}
        if buttons is not None and len(buttons):
            b = buttons.sort_values("tick").drop_duplicates("tick", keep="last")
            self._key_ticks = b["tick"].to_numpy(dtype=np.float64)
            for name in BUTTON_FIELDS:
                if name in b:
                    self._keys[name] = b[name].fillna(False).to_numpy(dtype=bool)

    @property
    def steamids(self) -> list[str]:
        return list(self._players)

    def player(self, steamid: str, tick: float) -> PlayerState | None:
        s = self._players.get(steamid)
        if s is None:
            return None
        v = s.at(tick)
        if v is None:
            return None
        x, y, z, yaw, alive, team = v
        return PlayerState(steamid, x, y, z, yaw, alive, team)

    def players(self, tick: float) -> list[PlayerState]:
        out = []
        for sid in self._players:
            st = self.player(sid, tick)
            if st is not None and st.team in (2, 3):
                out.append(st)
        return out

    def alive_at(self, steamid: str, tick: float) -> bool:
        st = self.player(steamid, tick)
        return bool(st and st.alive)

    def keys(self, tick: float) -> dict[str, bool]:
        if len(self._key_ticks) == 0 or tick < self._key_ticks[0]:
            return {k: False for k in BUTTON_FIELDS}
        j = int(np.searchsorted(self._key_ticks, tick, side="right")) - 1
        return {k: bool(self._keys[k][j]) if k in self._keys else False
                for k in BUTTON_FIELDS}

    @property
    def has_keys(self) -> bool:
        return bool(self._keys)

    def hud(self, tick: float) -> HudState:
        if self._hud is None or tick < self._hud_ticks[0]:
            return HudState()
        j = int(np.searchsorted(self._hud_ticks, tick, side="right")) - 1
        r = self._hud.iloc[j]

        def num(k, default=0):
            v = r.get(k)
            return default if v is None or (isinstance(v, float) and np.isnan(v)) else int(v)

        weapon = r.get("active_weapon_name")
        weapon = "" if weapon is None or (isinstance(weapon, float) and np.isnan(weapon)) else str(weapon)
        place = r.get("last_place_name")
        place = "" if place is None or (isinstance(place, float) and np.isnan(place)) else str(place)
        has_mag = weapon and not any(k in weapon.lower() for k in
                                     ("knife", "grenade", "flashbang", "molotov", "decoy", "c4",
                                      "incendiary", "bayonet", "karambit", "daggers", "zeus"))
        return HudState(
            alive=bool(r.get("is_alive")), health=num("health"), armor=num("armor_value"),
            helmet=bool(r.get("has_helmet")), money=num("balance"), weapon=weapon,
            ammo=num("active_weapon_ammo") if has_mag else -1, reserve=-1,
            scoped=bool(r.get("is_scoped")), place=place,
        )

    def utility_at(self, tick: float):
        u = self.utility
        return u.trails_at(tick), u.areas_at(tick), u.bursts_at(tick)

    @property
    def has_hud(self) -> bool:
        return self._hud is not None


# --- thrown utility ---------------------------------------------------------------

@dataclass
class Trail:
    kind: str
    steamid: str | None
    ticks: np.ndarray
    xs: np.ndarray
    ys: np.ndarray
    start: int
    landed: int     # tick the grenade stopped moving


@dataclass
class Area:
    kind: str       # "smoke" | "fire"
    start: int
    end: int
    x: float
    y: float
    steamid: str | None


class Utility:
    """Grenade flight paths, smokes, fires and flash/HE bursts by tick."""

    SMOKE_MAX_TICKS = 1450      # a smoke lasts ~22 s; cap events with a missing expiry
    TRAIL_FADE_TICKS = 48       # keep a landed grenade's path visible briefly
    BURST_TICKS = 24

    def __init__(self, data: dict[str, pd.DataFrame] | None):
        self.trails: list[Trail] = []
        self.areas: list[Area] = []
        self.bursts: list[tuple[int, float, float, str]] = []
        if not data:
            return
        paths = data.get("paths")
        if paths is not None and len(paths):
            for _, g in paths.groupby("entity"):
                t = g["tick"].to_numpy()
                # entity ids are reused: split where the ticks jump
                cuts = np.flatnonzero(np.diff(t) > 4) + 1
                for part in np.split(np.arange(len(t)), cuts):
                    if len(part) < 3:
                        continue
                    sub = g.iloc[part]
                    ticks = sub["tick"].to_numpy(dtype=np.int64)
                    xs, ys = sub["x"].to_numpy(dtype=float), sub["y"].to_numpy(dtype=float)
                    moving = np.hypot(np.diff(xs), np.diff(ys)) > 0.5
                    landed = ticks[-1]
                    still = 0
                    for i, m in enumerate(moving):
                        still = 0 if m else still + 1
                        if still >= 8:
                            landed = ticks[i - 7]
                            break
                    self.trails.append(Trail(sub["kind"].iloc[0], sub["steamid"].iloc[0], ticks, xs, ys,
                                             int(ticks[0]), int(landed)))
        for kind, key in (("smoke", "smokes"), ("fire", "fires")):
            df = data.get(key)
            if df is None:
                continue
            for _, r in df.iterrows():
                end = int(r["end"])
                if kind == "smoke":
                    end = min(end, int(r["start"]) + self.SMOKE_MAX_TICKS)
                self.areas.append(Area(kind, int(r["start"]), end, float(r["x"]), float(r["y"]), r["steamid"]))
        b = data.get("bursts")
        if b is not None:
            self.bursts = [(int(r["tick"]), float(r["x"]), float(r["y"]), str(r["kind"])) for _, r in b.iterrows()]

    def trails_at(self, tick: float) -> list[tuple[Trail, np.ndarray, np.ndarray, float]]:
        """(trail, xs, ys, alpha) for paths in flight or just landed."""
        out = []
        for tr in self.trails:
            if tick < tr.start or tick > tr.landed + self.TRAIL_FADE_TICKS:
                continue
            n = int(np.searchsorted(tr.ticks, min(tick, tr.landed), side="right"))
            if n < 2:
                continue
            alpha = 1.0 if tick <= tr.landed else 1 - (tick - tr.landed) / self.TRAIL_FADE_TICKS
            out.append((tr, tr.xs[:n], tr.ys[:n], alpha))
        return out

    def areas_at(self, tick: float) -> list[tuple[Area, float]]:
        """(area, fraction of its time left)."""
        return [(a, (a.end - tick) / max(1, a.end - a.start)) for a in self.areas if a.start <= tick < a.end]

    def bursts_at(self, tick: float) -> list[tuple[float, float, str, float]]:
        return [(x, y, k, 1 - (tick - t) / self.BURST_TICKS) for t, x, y, k in self.bursts
                if t <= tick < t + self.BURST_TICKS]
