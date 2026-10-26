import json
from types import SimpleNamespace

import pytest


def test_index_is_bound_to_video_and_rejects_stale_or_malformed_data(tmp_path):
    from povforge import video_index as vi
    video=tmp_path/'clip.mp4';video.write_bytes(b'video')
    vi.write(video,[{'at':2,'kind':'kill','round':1,'player':'A','weapon':'awp'},
                    {'at':float('nan'),'kind':'kill'},{'at':-2,'kind':'round'}])
    assert vi.read(video)==[{'at':2.0,'kind':'kill','round':1,'player':'A','weapon':'awp'}]
    video.write_bytes(b'changed video');assert vi.read(video)==[]
    vi.sidecar(video).write_text('{broken');assert vi.read(video)==[]


def test_source_mapping_handles_actual_seek_and_inline_replays(tmp_path):
    from povforge import video_index as vi
    from povforge.model import Player,Plan,Segment
    job=tmp_path/'job';job.mkdir();clip=job/'clips'/'clip_000.mp4'
    plan=Plan('x.dem','de_test',10,Player('a','Alice'),[Segment(1,100,300,'round_end')])
    (job/'recorded.json').write_text('{"r01":90}')
    (job/'event-index.json').write_text(json.dumps([{'tick':150,'kind':'kill','round':1,'weapon':'awp','player':'Alice'},
                                                 {'tick':200,'kind':'death','round':1,'player':'Alice'}]))
    windows={('x.dem','a',1):[(clip,2,15,[4])]};contexts={('x.dem','a',1):(job,plan)}
    order=vi.index_order([(clip,2,7,[4]),(tmp_path/'replay.mp4',0,1,[]),(clip,7,15,[])],windows,contexts)
    events=vi.flatten(order.markers,[5,1,8])
    assert next(e['at'] for e in events if e['kind']=='kill')==4
    assert next(e['at'] for e in events if e['kind']=='death')==10
    assert any(e['kind']=='replay' and e['at']==5 for e in events)


def test_effect_timeline_accounts_for_card_slow_motion_and_overlap(tmp_path):
    from povforge import video_index as vi
    from povforge import effects
    from povforge.effects import Moment
    moments=[Moment(tmp_path/'a.mp4',0,5,[2],events=[{'at':2,'kind':'kill','round':1}]),
             Moment(tmp_path/'b.mp4',0,4,[],events=[{'at':1,'kind':'death','round':2}])]
    fx=effects.normalize({'intro':'title','kill_slowmo':True,'slowmo_speed':.5})
    events=vi.effect_events(moments,[[2],[]],fx,[('card',None),('moment',0),('moment',1)],[2.5,6,4],[.4,.3])
    mapped=effects.mapped(2,effects.time_map(5,[2],.5))
    assert events[0]['at']==pytest.approx(2.5-.4+mapped)
    assert events[1]['at']==pytest.approx(2.5-.4+6-.3+1)


def test_recorded_event_metadata_and_publish_keep_index(tmp_path):
    from povforge import video_index as vi
    from povforge.model import Player,Round,Death
    from povforge import pipeline
    from povforge.config import Config
    data=SimpleNamespace(rounds=[Round(1,0,100)],players=[Player('a','A'),Player('b','B')],
        deaths=[Death(20,'b','a','awp',True),Death(40,'a','b','ak47')],tickrate=10,last_tick=100)
    job=tmp_path/'job';job.mkdir();vi.record_events(job,data,'a')
    rows=json.loads((job/'event-index.json').read_text())
    assert [e['kind'] for e in rows]==['kill','death'] and rows[0]['weapon']=='awp'
    video=job/'a.mp4';video.write_bytes(b'video');vi.write(video,[{'at':2,'kind':'kill'}])
    result=pipeline.publish(Config(output_dir=tmp_path/'out'),job,video)
    assert vi.read(result)==[{'at':2.0,'kind':'kill'}]
