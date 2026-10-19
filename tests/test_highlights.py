from types import SimpleNamespace as NS

from povforge import highlights as H
from povforge.extras import kill_windows
from povforge.model import Death, Player, Plan, Round, Segment


def test_titles():
    assert H.chapter_title(18, H.RoundHighlight(18, 5, 3), "zh") == "第18回合 · ACE"
    assert H.chapter_title(7, H.RoundHighlight(7, 3, 1, clutch=2, won=True), "zh") == "第7回合 · 三杀 · 1v2 残局"
    assert H.chapter_title(4, H.RoundHighlight(4, 1, 1), "en") == "Round 4"
    assert H.chapter_title(9, H.RoundHighlight(9, 2, 0), "en") == "Round 9 · 2K"
    assert H.chapter_title(3, None) == "第3回合"


class FakeTrack:
    """Three players per team, all alive at freeze end."""
    def __init__(self):
        self.ps = [NS(steamid=f"a{i}", team=3, alive=True) for i in range(3)] + \
                  [NS(steamid=f"b{i}", team=2, alive=True) for i in range(3)]

    def player(self, sid, tick):
        return next(p for p in self.ps if p.steamid == sid)

    def players(self, tick):
        return self.ps


def test_clutch_and_kills():
    deaths = [Death(110, "a1", "b0", "ak47"), Death(120, "a2", "b1", "ak47"),   # me (a0) left alone vs 3
              Death(130, "b0", "a0", "ak47", True), Death(140, "b1", "a0", "ak47"), Death(150, "b2", "a0", "ak47")]
    demo = NS(rounds=[Round(1, 100, 200)], deaths=deaths, winners={200: 3})
    (h,) = H.analyse(demo, "a0", FakeTrack())
    assert (h.kills, h.headshots, h.clutch, h.won) == (3, 1, 3, True)
    lost = NS(rounds=[Round(1, 100, 200)], deaths=deaths, winners={200: 2})
    assert H.analyse(lost, "a0", FakeTrack())[0].clutch == 0


def test_kill_windows_merge_close_kills():
    seg = Segment(1, 0, 64 * 60, "round_end")
    plan = Plan("x.dem", "de_cache", 64, Player("1", "p"), [seg])
    kills = [(64 * 10, False), (64 * 12, True), (64 * 30, False)]   # 10 s and 12 s merge; 30 s alone
    w = kill_windows(plan, {}, kills, [60.0], before=4, after=1.5, gap=2.5)
    assert w == [(0, 6.0, 13.5), (0, 26.0, 31.5)]


def test_round_table_kills_and_won_clutch():
    from povforge.highlights import is_highlight, round_table
    from povforge.model import Death, Round
    r = Round(1, 100, 1000)
    sides = {1: {"me": 3, "mate": 3, "e1": 2, "e2": 2, "e3": 2}}
    deaths = [Death(200, "mate", "e1", "ak47"),          # I'm alone vs 3
              Death(300, "e1", "me", "m4a1", True),
              Death(400, "e2", "me", "m4a1"),
              Death(500, "e3", "me", "m4a1", True),
              Death(1200, "x", "me", "knife")]           # after the round: not counted
    t = round_table([r], deaths, {1000: 3}, sides)
    me = t["me"][0]
    assert (me.kills, me.headshots, me.clutch, me.won) == (3, 2, 3, True)
    assert t["e1"][0].kills == 1 and t["e1"][0].won is False and t["e1"][0].clutch == 0
    assert is_highlight(me.kills, me.clutch) and not is_highlight(2, 0) and is_highlight(0, 1)


def test_lost_clutch_is_not_a_clutch():
    from povforge.highlights import round_table
    from povforge.model import Death, Round
    sides = {1: {"me": 3, "mate": 3, "e1": 2}}
    t = round_table([Round(1, 0, 900)], [Death(10, "mate", "e1", "ak47"), Death(20, "me", "e1", "ak47")],
                    {900: 2}, sides)
    assert t["me"][0].clutch == 0                 # lost after being left alone
    assert t["e1"][0].clutch == 2                 # e1 alone vs two and won
