import json
from types import SimpleNamespace

import pytest

from povforge.model import Death,Player,Round
from povforge.reel import ReelItem,load_spec
from povforge.reel_events import select_views


def demo():
    return SimpleNamespace(tickrate=10,players=[Player('a','A'),Player('b','B')],
        rounds=[Round(1,0,500)],deaths=[Death(100,'b','a','ak47'),Death(150,'c','a','awp'),
        Death(350,'d','a','ak47')])


@pytest.mark.parametrize('mode',['kill_events','kills_deaths'])
def test_weapon_match_keeps_whole_mixed_multikill_but_not_unrelated_window(mode):
    item=ReelItem('x.dem','a',1,mode,weapons=['weapon_awp'])
    result=select_views([item],{'x.dem':(demo(),{})},5,3)
    assert [(v.start_tick,v.end_tick,v.kill_ticks) for v in result]==[(50,180,(100,150))]


def test_weapon_filter_roundtrip_duel_and_no_matches(tmp_path):
    path=tmp_path/'spec.json'
    path.write_text(json.dumps({'items':[{'demo':'x.dem','steamid':'a','round':1,'weapons':['AWP','awp']}]}))
    assert load_spec(path)[1][0].weapons==('awp',)
    sides={1:{'a':2,'b':3}}
    data=demo(); data.deaths=[Death(100,'b','a','awp')]
    views=select_views([ReelItem('x.dem','a',1,'duel','b',weapons=['awp'])],{'x.dem':(data,sides)},5,3)
    assert [v.steamid for v in views]==['a','b']
    assert select_views([ReelItem('x.dem','a',1,'kill_events',weapons=['deagle'])],{'x.dem':(data,{})},5,3)==[]


@pytest.mark.parametrize('bad',[['awp;command'], 'awp', ['a'*100], [None]])
def test_filter_rejects_invalid_weapon_values(bad):
    with pytest.raises(ValueError):
        ReelItem('x.dem','a',1,weapons=bad)


def test_queue_and_recovery_preserve_weapon_filter(tmp_path):
    from povforge.gui.server import Queue
    from test_gui import FakeJob
    queue=Queue(FakeJob(),{},store=tmp_path/'queue.json')
    queue.add_reel('AWP',[{'demo':'x.dem','steamid':'a','round':1,'weapons':['awp']}])
    restored=Queue(FakeJob(),{},store=tmp_path/'queue.json')
    assert restored.snapshot()['items'][0]['reel'][0]['weapons']==['awp']
