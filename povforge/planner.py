"""Turn rounds and deaths into the list of clips to record.

Rules (one clip per round):
  * a clip starts when freeze time ends, so buy time, timeouts and halftime
    are never recorded;
  * it stops a moment after the followed player dies, so we jump straight to
    the next round instead of watching teammates;
  * if the player survives, it stops a moment after the round is decided.
"""

from __future__ import annotations

import bisect
from dataclasses import dataclass
from typing import Callable, Iterable

from .model import Death, Round, Segment


@dataclass
class PlanOptions:
    pre_roll_seconds: float = 0.0     # extra time before freeze end
    post_death_seconds: float = 2.0   # keep the kill feed on screen briefly
    post_round_seconds: float = 2.0   # show the round result briefly
    min_segment_seconds: float = 1.0  # drop clips shorter than this


def build_rounds(
    freeze_end_ticks: Iterable[int],
    round_end_ticks: Iterable[int],
    match_start_tick: int,
    last_tick: int,
) -> list[Round]:
    """Pair every freeze-end with the round end that follows it.

    Warmup and knife rounds before the (last) match start announcement are
    ignored. A round with no end event (demo cut off) ends at the last tick.
    """
    freezes = sorted(t for t in set(freeze_end_ticks) if t >= match_start_tick)
    ends = sorted(set(round_end_ticks))
    rounds: list[Round] = []
    for i, f in enumerate(freezes):
        next_f = freezes[i + 1] if i + 1 < len(freezes) else None
        j = bisect.bisect_right(ends, f)
        end = ends[j] if j < len(ends) else None
        if end is None or (next_f is not None and end > next_f):
            if next_f is not None:
                # No end event before the next round started (e.g. a restart):
                # not a real round, skip it.
                continue
            end = last_tick
        rounds.append(Round(number=len(rounds) + 1, freeze_end_tick=f, end_tick=end))
    return rounds


def plan_segments(
    rounds: list[Round],
    deaths: list[Death],
    player_steamid: str,
    tickrate: float,
    last_tick: int,
    opts: PlanOptions | None = None,
    alive_at: Callable[[int], bool] | None = None,
) -> list[Segment]:
    """One segment per round the player actually played in."""
    opts = opts or PlanOptions()
    pre = round(opts.pre_roll_seconds * tickrate)
    post_death = round(opts.post_death_seconds * tickrate)
    post_round = round(opts.post_round_seconds * tickrate)
    min_len = round(opts.min_segment_seconds * tickrate)

    my_deaths = sorted(d.tick for d in deaths if d.victim_steamid == player_steamid)

    segments: list[Segment] = []
    for r in rounds:
        # Skip rounds where the player isn't in the game (disconnected, not
        # yet substituted in, spectating...).
        probe = min(r.freeze_end_tick + 1, last_tick)
        if alive_at is not None and not alive_at(probe):
            continue

        start = max(0, r.freeze_end_tick - pre)
        round_stop = min(r.end_tick + post_round, last_tick)

        i = bisect.bisect_left(my_deaths, r.freeze_end_tick)
        death = my_deaths[i] if i < len(my_deaths) else None

        if death is not None and death <= r.end_tick:
            end, why = min(death + post_death, round_stop), "death"
        elif r.end_tick >= last_tick:
            end, why = last_tick, "demo_end"
        else:
            end, why = round_stop, "round_end"
            if death is not None and death < end:
                # Died after the round was decided (exit frag): cut there.
                end = min(death + post_death, end)

        if end - start < min_len:
            continue
        segments.append(Segment(r.number, start, end, why))
    return segments
