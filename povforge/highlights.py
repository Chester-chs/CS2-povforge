"""What happened in each round for the followed player: kills, headshots,
clutches. Used for chapter titles, the highlight video and the upload kit."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .demo import DemoData
from .timeline import Track


@dataclass
class RoundHighlight:
    number: int
    kills: int
    headshots: int
    clutch: int = 0        # N of a won 1vN (the player was the last one alive on the team)
    won: bool | None = None

    @property
    def score(self) -> int:
        """Rough interest score: multi-kills and clutches first."""
        return self.kills * 10 + self.headshots + (25 * self.clutch if self.clutch else 0)


def analyse(demo: DemoData, steamid: str, track: Track) -> list[RoundHighlight]:
    out = []
    deaths = sorted(demo.deaths, key=lambda d: d.tick)
    for r in demo.rounds:
        in_round = [d for d in deaths if r.freeze_end_tick <= d.tick <= r.end_tick]
        mine = [d for d in in_round if d.attacker_steamid == steamid and d.victim_steamid != steamid]
        h = RoundHighlight(r.number, len(mine), sum(1 for d in mine if d.headshot))
        me = track.player(steamid, r.freeze_end_tick)
        winner = demo.winners.get(r.end_tick)
        if me is not None and me.team in (2, 3):
            h.won = None if winner is None else winner == me.team
            h.clutch = _clutch(in_round, steamid, me.team, track, r.freeze_end_tick) if h.won else 0
        out.append(h)
    return out


def _clutch(deaths, steamid: str, my_team: int, track: Track, tick: int) -> int:
    """Enemies alive when the player became the team's last one standing (0 = never)."""
    alive = {p.steamid: p.team for p in track.players(tick) if p.alive}
    if steamid not in alive:
        return 0
    for d in deaths:
        alive.pop(d.victim_steamid, None)
        if steamid not in alive:
            return 0
        mates = [s for s, t in alive.items() if t == my_team and s != steamid]
        if not mates:
            # count enemies alive at this moment (before the player's later kills)
            return sum(1 for t in alive.values() if t != my_team)
    return 0


def save(path: Path, rows: list[RoundHighlight]) -> None:
    path.write_text(json.dumps([asdict(r) for r in rows], indent=1), encoding="utf-8")


def load(path: Path) -> dict[int, RoundHighlight]:
    if not path.exists():
        return {}
    return {r["number"]: RoundHighlight(**r) for r in json.loads(path.read_text(encoding="utf-8"))}


KILL_NAMES = {
    "zh": {2: "双杀", 3: "三杀", 4: "四杀", 5: "ACE"},
    "en": {2: "2K", 3: "3K", 4: "4K", 5: "ACE"},
}


def describe(h: RoundHighlight | None, lang: str = "zh") -> str:
    """'三杀 · 1v2 残局' / '3K · 1v2 clutch'; empty for an ordinary round."""
    if h is None:
        return ""
    parts = []
    names = KILL_NAMES.get(lang, KILL_NAMES["en"])
    if h.kills >= 2:
        parts.append(names[min(h.kills, 5)])
    if h.clutch:
        parts.append(f"1v{h.clutch} " + ("残局" if lang == "zh" else "clutch"))
    return " · ".join(parts)


def chapter_title(number: int, h: RoundHighlight | None, lang: str = "zh") -> str:
    base = f"第{number}回合" if lang == "zh" else f"Round {number}"
    extra = describe(h, lang)
    return f"{base} · {extra}" if extra else base
