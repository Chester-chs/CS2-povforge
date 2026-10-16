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


class Track:
    """Fast per-tick lookups over the parsed position and button tables."""

    def __init__(self, positions: pd.DataFrame, buttons: pd.DataFrame | None = None):
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
