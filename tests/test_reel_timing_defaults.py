from types import SimpleNamespace

import pytest

from povforge.config import Config
from povforge.model import Death, Player, Plan, Round, Segment
from povforge.reel import ReelItem, _cut_points
from povforge.reel_events import select_views


@pytest.mark.parametrize('mode', ['kill_events', 'kills_deaths'])
def test_five_seconds_before_three_after_and_continuous_multikill(mode):
    h = Config().highlights
    data = SimpleNamespace(tickrate=10, players=[Player('a','A'),Player('b','B')],
        rounds=[Round(1,0,500)], deaths=[Death(100,'b','a','ak47'),
        Death(175,'c','a','ak47'),Death(300,'d','a','awp')])
    views = select_views([ReelItem('x.dem','a',1,mode)],{'x.dem':(data,{})},h.before,h.after)
    assert [(v.start_tick,v.end_tick,v.event_ticks) for v in views] == [
        (50,205,(100,175)),(250,330,(300,))]


def test_highlight_round_preserves_all_time_between_kills(tmp_path, monkeypatch):
    from povforge import reel
    cfg = Config()
    clip = tmp_path/'clip.mp4'; clip.write_bytes(b'fixture')
    (tmp_path/'kills.json').write_text('[[100,false],[300,true]]')
    plan = Plan('x.dem','de_x',10,Player('a','A'),[Segment(1,0,500,'round_end')])
    monkeypatch.setattr(reel,'probe',lambda *a:SimpleNamespace(duration=50))
    monkeypatch.setattr(reel,'actual_starts',lambda _: {})
    assert _cut_points(cfg,tmp_path,{1},plan,[clip])[1] == [(clip,5.0,33.0,[5.0,25.0])]


def test_event_padding_clips_at_round_boundaries():
    h = Config().highlights
    data = SimpleNamespace(tickrate=10,players=[Player('a','A'),Player('b','B')],
        rounds=[Round(1,20,200)],deaths=[Death(30,'b','a','ak47'),Death(195,'c','a','awp')])
    views = select_views([ReelItem('x.dem','a',1,'kill_events')],{'x.dem':(data,{})},h.before,h.after)
    assert [(v.start_tick,v.end_tick) for v in views] == [(20,60),(145,201)]
