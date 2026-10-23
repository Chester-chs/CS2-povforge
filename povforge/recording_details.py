"""Small reusable event and timing index for recording selection, not capture."""
from .demo import event_round_end
from .planner import plan_segments
from .reel_events import first_person_kills


def build(demo):
    events = []
    rounds = []
    for r in demo.rounds:
        stop = event_round_end(demo, r)
        deaths = sorted((d for d in demo.deaths if r.freeze_end_tick <= d.tick < stop), key=lambda d: d.tick)
        supported = set(first_person_kills(deaths))
        rounds.append({'number': r.number, 'start': 0, 'end': (stop-r.freeze_end_tick)/demo.tickrate})
        for d in deaths:
            events.append({'round': r.number, 'tick': d.tick, 'time': (d.tick-r.freeze_end_tick)/demo.tickrate,
                'attacker': d.attacker_steamid, 'victim': d.victim_steamid,
                'weapon': d.weapon or '', 'headshot': bool(d.headshot), 'pov': d in supported})
    seconds = {}
    for p in demo.players:
        segments = plan_segments(demo.rounds, demo.deaths, p.steamid, demo.tickrate, demo.last_tick)
        by_round = {s.round_number: s.duration_seconds(demo.tickrate) for s in segments}
        seconds[p.steamid] = [by_round.get(r.number, 0) for r in demo.rounds]
    return {'version': 1, 'rounds': rounds, 'events': events, 'seconds': seconds}
