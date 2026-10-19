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
        return score(self.kills, self.headshots, self.clutch)


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


def score(kills: int, headshots: int, clutch: int) -> int:
    """Rough interest score: multi-kills and clutches first."""
    return kills * 10 + headshots + (25 * clutch if clutch else 0)


def is_highlight(kills: int, clutch: int) -> bool:
    """What the highlight reel picks by default: 3+ kills, or a won clutch (1v1 counts)."""
    return kills >= 3 or clutch >= 1


def round_table(rounds, deaths, winners: dict[int, int],
                sides: dict[int, dict[str, int]]) -> dict[str, list[RoundHighlight]]:
    """Kills, headshots and won clutches of every player in every round, from
    the deaths and who was alive on which side when the round started."""
    deaths = sorted(deaths, key=lambda d: d.tick)
    everyone = {sid for side in sides.values() for sid in side}
    table = {sid: [] for sid in everyone}
    for r in rounds:
        alive = dict(sides.get(r.number, {}))
        winner = winners.get(r.end_tick)
        rows = {sid: RoundHighlight(r.number, 0, 0) for sid in everyone}
        last_alone: dict[str, int] = {}        # player -> enemies alive when they became the last one

        def check_last() -> None:
            for team in (2, 3):
                left = [s for s, t in alive.items() if t == team]
                if len(left) == 1 and left[0] not in last_alone:
                    enemies = sum(1 for t in alive.values() if t != team)
                    if enemies:
                        last_alone[left[0]] = enemies

        check_last()
        for d in deaths:
            if not (r.freeze_end_tick <= d.tick <= r.end_tick):
                continue
            a = d.attacker_steamid
            if a in rows and a != d.victim_steamid and alive.get(a) != alive.get(d.victim_steamid, -1):
                rows[a].kills += 1
                rows[a].headshots += int(d.headshot)
            alive.pop(d.victim_steamid, None)
            check_last()
        for sid, row in rows.items():
            team = sides.get(r.number, {}).get(sid)
            if team is not None and winner is not None:
                row.won = winner == team
                if row.won and sid in last_alone:
                    row.clutch = last_alone[sid]
            table[sid].append(row)
    return table


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
