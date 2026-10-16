"""Plain data types shared across the pipeline.

Everything here is JSON-serialisable so a job (plan, segments) can be saved to
disk and resumed later, e.g. render overlays today and record tomorrow.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Player:
    steamid: str
    name: str


@dataclass(frozen=True)
class Round:
    number: int            # 1-based, counted from the live match start
    freeze_end_tick: int   # players can move from here
    end_tick: int          # round_end event (winner decided)


@dataclass(frozen=True)
class Death:
    tick: int
    victim_steamid: str
    attacker_steamid: str | None
    weapon: str | None


@dataclass(frozen=True)
class Segment:
    """One recorded clip: a single round from the target player's eyes."""

    round_number: int
    start_tick: int
    end_tick: int
    ends_by: str           # "death" | "round_end" | "demo_end"

    def duration_seconds(self, tickrate: float) -> float:
        return (self.end_tick - self.start_tick) / tickrate


@dataclass
class Plan:
    demo_path: str
    map_name: str
    tickrate: float
    player: Player
    segments: list[Segment] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Plan":
        return cls(
            demo_path=d["demo_path"],
            map_name=d["map_name"],
            tickrate=d["tickrate"],
            player=Player(**d["player"]),
            segments=[Segment(**s) for s in d["segments"]],
        )

    def total_seconds(self) -> float:
        return sum(s.duration_seconds(self.tickrate) for s in self.segments)
