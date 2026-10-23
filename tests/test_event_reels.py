import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from povforge import reel, pipeline
from povforge.config import Config
from povforge.model import Death, Player, Round, Plan, Segment


def sample():
    return SimpleNamespace(tickrate=10, players=[Player('a', 'A'), Player('b', 'B'), Player('c', 'C')],
        rounds=[Round(1, 0, 200), Round(2, 210, 400)],
        deaths=[Death(300, 'a', 'b', 'ak47'), Death(80, 'c', 'a', 'ak47'),
                Death(100, 'b', 'a', 'ak47'), Death(150, 'a', 'c', 'ak47')])


def test_solo_events_keep_selected_first_person_merge_overlap_and_sort():
    from povforge.reel_events import select_views
    items = [reel.ReelItem('test.dem', 'a', 2, 'kills_deaths'),
             reel.ReelItem('test.dem', 'a', 1, 'kills_deaths')]
    views = select_views(items, {'test.dem': (sample(), {})}, 3, 1)
    assert [(v.round, v.steamid, v.start_tick, v.end_tick, v.kill_ticks) for v in views] == [
        (1, 'a', 50, 110, (80, 100)), (1, 'a', 120, 160, ()), (2, 'a', 270, 310, ())]
    kills = select_views([reel.ReelItem('test.dem', 'a', 1, 'kill_events')], {'test.dem': (sample(), {})}, 3, 1)
    assert [(v.steamid, v.event_ticks, v.kill_ticks) for v in kills] == [('a', (80, 100), (80, 100))]


def test_deaths_only_mode_is_no_longer_accepted():
    with pytest.raises(ValueError, match='mode'):
        reel.ReelItem('test.dem', 'a', 1, 'deaths')


@pytest.mark.parametrize('mode', ['kill_events', 'kills_deaths', 'duel'])
def test_posthumous_kills_do_not_request_an_unavailable_pov(mode, monkeypatch, capsys):
    from povforge import reel_events
    data = sample()
    data.deaths = [Death(50, 'b', 'a', 'ak47'), Death(80, 'a', 'c', 'ak47'),
                   Death(150, 'b', 'a', 'inferno')]
    sides = {1: {'a': 2, 'b': 3, 'c': 3}}
    views = reel_events.select_views([reel.ReelItem('test.dem', 'a', 1, mode, 'b')],
                                    {'test.dem': (data, sides)}, 3, 1)
    assert all(150 not in v.event_ticks for v in views)
    assert 'posthumous' in capsys.readouterr().out
    assert [e['tick'] for e in reel_events.duel_events(data, sides)] == [50, 80]


def test_only_posthumous_kills_fail_before_recording(monkeypatch):
    from povforge import reel_events
    data = sample()
    data.deaths = [Death(80, 'a', 'c', 'ak47'), Death(150, 'b', 'a', 'hegrenade')]
    monkeypatch.setattr(reel_events, 'load_sources', lambda *a: {'test.dem': (data, {})})
    monkeypatch.setattr(pipeline, 'make_recording', lambda *a: pytest.fail('must fail before CS2'))
    with pytest.raises(ValueError, match='first-person'):
        reel.run(Config(), 'Kills', [reel.ReelItem('test.dem', 'a', 1, 'kill_events')])


def test_old_inspection_cache_is_rebuilt_for_first_person_event_filter(tmp_path, monkeypatch):
    import hashlib
    from povforge.gui import server
    monkeypatch.setenv('POVFORGE_STATE', str(tmp_path / 'state'))
    monkeypatch.setattr(server, '_inspect_cache', {})
    demo = tmp_path / 'match.dem'
    demo.write_bytes(b'demo')
    st = demo.stat()
    old_key = f'{demo.resolve()}|{st.st_mtime}|{st.st_size}|v3'
    saved = server.app_dir() / 'demo-info' / (hashlib.sha1(old_key.encode()).hexdigest() + '.json')
    saved.parent.mkdir(parents=True)
    saved.write_text(json.dumps({'rounds_event_k': [1], 'duels': [{'tick': 150}]}))
    fresh = {'rounds_event_k': [0], 'duels': []}
    calls = []
    def parse(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0, stdout=json.dumps(fresh), stderr='')
    monkeypatch.setattr(server.subprocess, 'run', parse)
    assert server.inspect_isolated(str(demo), tmp_path) == fresh
    assert len(calls) == 1
    server._inspect_cache.clear()
    assert server.inspect_isolated(str(demo), tmp_path) == fresh
    assert len(calls) == 1, 'new inspection should persist for the next app session'


def test_duel_only_mutual_enemy_kills_each_a_then_b_and_halftime_swap():
    from povforge.reel_events import select_views, duel_events
    sides = {1: {'a': 2, 'b': 3, 'c': 2}, 2: {'a': 3, 'b': 2, 'c': 3}}
    assert [(e['round'], e['tick']) for e in duel_events(sample(), sides)] == [(1, 100), (2, 300)]
    items = [reel.ReelItem('test.dem', 'a', r, 'duel', 'b') for r in [2, 1]]
    views = select_views(items, {'test.dem': (sample(), sides)}, 3, 1)
    assert [(v.round, v.steamid, v.event_ticks, v.kill_ticks) for v in views] == [
        (1, 'a', (100,), (100,)), (1, 'b', (100,), ()),
        (2, 'a', (300,), ()), (2, 'b', (300,), (300,))]
    swapped = select_views([reel.ReelItem('test.dem', 'b', 1, 'duel', 'a')], {'test.dem': (sample(), sides)}, 3, 1)
    assert [v.steamid for v in swapped] == ['b', 'a']


@pytest.mark.parametrize('opponent,sides', [('a', {1: {'a': 2}}), ('b', {1: {'a': 2, 'b': 2}}), ('b', {})])
def test_duel_invalid_or_unknown_team_never_records(opponent, sides, monkeypatch):
    from povforge import reel_events
    monkeypatch.setattr(reel_events, 'load_sources', lambda *args: {'test.dem': (sample(), sides)})
    monkeypatch.setattr(pipeline, 'make_recording', lambda *args: pytest.fail('must validate before recording'))
    with pytest.raises(ValueError):
        reel.run(Config(), 'Duel', [reel.ReelItem('test.dem', 'a', 1, 'duel', opponent)])


def test_event_spec_roundtrip_and_queue_preserves_modes(tmp_path, monkeypatch):
    from povforge.gui.server import Queue
    item = {'demo': 'test.dem', 'steamid': 'a', 'round': 1, 'mode': 'duel', 'opponent': 'b'}
    path = tmp_path / 'spec.json'
    path.write_text(json.dumps({'items': [item]}))
    assert reel.load_spec(path)[1][0] == reel.ReelItem(**item)
    queue = object.__new__(Queue)
    monkeypatch.setattr(queue, '_add', lambda data: data)
    queued = queue.add_reel('Duel', [item])
    assert queued['reel'][0]['mode'] == 'duel'
    assert queued['reel'][0]['opponent'] == 'b'


def test_event_cut_respects_actual_start_duration_and_kill_anchors(tmp_path):
    from povforge.reel_events import View, cut_view
    view = View('test.dem', 'a', 1, 50, 110, (80, 100), (80, 100))
    plan = Plan('test.dem', 'de_test', 10, Player('a', 'A'), [Segment(1, 40, 120, 'round_end')])
    span = cut_view(view, plan, tmp_path / 'clip.mp4', 45, 8)
    assert span[1:] == (0.5, 6.5, [3, 5])
    with pytest.raises(ValueError, match='event'):
        cut_view(view, plan, tmp_path / 'clip.mp4', 90, 1)


def test_exit_deaths_belong_to_original_round_and_end_event_is_inside_clip(tmp_path):
    from povforge.demo import event_round_end
    from povforge.reel_events import select_views, cut_view
    data = sample()
    data.last_tick = 450
    data.round_starts = [0, 205]
    data.deaths = [Death(200, 'b', 'a', 'ak47'), Death(202, 'a', 'c', 'ak47')]
    assert event_round_end(data, data.rounds[0]) == 205
    views = select_views([reel.ReelItem('test.dem','a',1,'kills_deaths')], {'test.dem':(data,{})}, 3, 1)
    assert views[0].event_ticks == (200,202)
    assert views[0].end_tick == 205
    plan = Plan('test.dem','de_test',10,Player('a','A'),[Segment(1,0,205,'death')])
    assert cut_view(views[0],plan,tmp_path/'clip.mp4',0,20.5)[2] == 20.5
    with pytest.raises(ValueError,match='event'):
        cut_view(views[0],plan,tmp_path/'clip.mp4',0,20.2)


def test_event_planning_keeps_exit_event_after_normal_round_tail(tmp_path,monkeypatch):
    from test_audit_plan_identity import fake_parser
    fake_parser(monkeypatch)
    data=sample();data.last_tick=500;data.round_starts=[0,250]
    data.rounds[1] = Round(2,260,400)
    data.deaths=[Death(240,'a','b','ak47')]
    data.map_name='de_test'
    monkeypatch.setattr(pipeline,'load_demo',lambda _:data)
    monkeypatch.setattr(pipeline,'plan_segments',lambda *a,**kw:[Segment(1,0,220,'round_end')])
    demo=tmp_path/'match.dem';demo.write_bytes(b'demo')
    plan,_=pipeline.make_plan(Config(output_dir=tmp_path/'out'),demo,'a',{1},'events',(3,1),event_ticks=[240])
    assert plan.segments[0].end_tick == 250


def test_event_selection_is_part_of_plan_cache_identity(tmp_path, monkeypatch):
    from test_audit_plan_identity import fake_parser
    fake_parser(monkeypatch)
    cfg = Config(output_dir=tmp_path / 'output')
    demo = tmp_path / 'test.dem'
    demo.write_bytes(b'demo')
    first, job1 = pipeline.make_plan(cfg, demo, '111', {1}, 'events', (0.1, 0.1), event_ticks=[80])
    second, job2 = pipeline.make_plan(cfg, demo, '111', {1}, 'events', (0.1, 0.1), event_ticks=[170])
    assert job1 != job2
    assert first.segments != second.segments
    assert pipeline.make_plan(cfg, demo, '111', {1}, 'events', (0.1, 0.1), event_ticks=[80])[1] == job1


def test_reused_and_new_recordings_render_each_encounter_a_then_b(tmp_path, monkeypatch):
    """Render actual distinct-colour POV clips and inspect the joined pixels."""
    import shutil
    import subprocess
    from povforge import reel_events
    if not shutil.which('ffmpeg'):
        pytest.skip('FFmpeg required')
    cfg = Config(output_dir=tmp_path / 'output')
    cfg.record.width, cfg.record.height, cfg.record.fps = 160, 90, 30
    cfg.compose.preset = 'ultrafast'
    cfg.highlights.before = cfg.highlights.after = 0.5
    data = sample()
    sides = {1: {'a': 2, 'b': 3}, 2: {'a': 3, 'b': 2}}
    jobs = {}
    for sid, colour in [('a','red'),('b','blue')]:
        job = tmp_path / sid
        (job/'clips').mkdir(parents=True)
        plan = Plan('test.dem','de_test',10,Player(sid,sid),[Segment(1,0,200,'round_end'),Segment(2,210,400,'round_end')])
        (job/'plan.json').write_text(json.dumps(plan.to_dict()))
        for i in range(2):
            subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i',f'color={colour}:s=160x90:r=30:d=20',
                            '-c:v','libx264','-preset','ultrafast',str(job/'clips'/f'clip_{i:03d}.mp4')],check=True)
        jobs[sid] = job
    monkeypatch.setattr(reel_events,'load_sources',lambda *args:{'test.dem':(data,sides)})
    monkeypatch.setattr(pipeline,'whole_match_job',lambda cfg,demo,sid:jobs[sid] if sid=='a' else None)
    plans = []
    def make_plan(cfg,demo,sid,rounds,**kw):
        plans.append((sid,rounds,kw['event_ticks']))
        return pipeline.load_plan(jobs[sid]),jobs[sid]
    monkeypatch.setattr(pipeline,'make_plan',make_plan)
    monkeypatch.setattr(pipeline,'make_recording',lambda cfg,job,placeholder:[job/'clips'/f'clip_{i:03d}.mp4' for i in range(2)])
    out = reel.run(cfg,'Duel',[reel.ReelItem('test.dem','a',r,'duel','b') for r in [2,1]])
    assert plans == [('b',{1,2},[100,300])]
    assert out.exists()
    for sec, expected in [(0.5,'red'),(1.5,'blue'),(2.5,'red'),(3.5,'blue')]:
        pixels = subprocess.run(['ffmpeg','-v','error','-ss',str(sec),'-i',str(out),'-frames:v','1',
                                 '-vf','scale=1:1','-f','rawvideo','-pix_fmt','rgb24','-'],check=True,capture_output=True).stdout
        red,_,blue = pixels[:3]
        assert (red > blue) == (expected=='red')
    assert not (pipeline.work_root(cfg)/'reel pieces'/'Duel').exists()


def test_fallback_cannot_mix_old_clip_with_new_tick_context(tmp_path, monkeypatch):
    from povforge import reel_events
    cfg=Config(output_dir=tmp_path/'out')
    cfg.highlights.before=cfg.highlights.after=0.5
    full,new=tmp_path/'full',tmp_path/'new'
    for job in (full,new):
        (job/'clips').mkdir(parents=True)
        (job/'clips/clip_000.mp4').write_bytes(b'clip')
    plan=Plan('test.dem','de_test',10,Player('a','A'),[Segment(1,0,200,'death')])
    monkeypatch.setattr(reel_events,'load_sources',lambda *a:{'test.dem':(sample(),{})})
    monkeypatch.setattr(pipeline,'whole_match_job',lambda *a:full)
    monkeypatch.setattr(pipeline,'load_plan',lambda *a:plan)
    monkeypatch.setattr(pipeline,'make_plan',lambda *a,**kw:(plan,new))
    monkeypatch.setattr(pipeline,'make_recording',lambda *a:[new/'clips/clip_000.mp4'])
    monkeypatch.setattr(reel_events,'actual_starts',lambda job:{reel_events.clip_id(plan.segments[0]):0 if job==full else 100})
    monkeypatch.setattr(reel_events,'probe',lambda path,*a:SimpleNamespace(duration=12 if path.parent.parent==full else 10))
    monkeypatch.setattr(reel,'_camera_order',lambda *a:pytest.fail('mixed tick contexts must not reach replay planning'))
    with pytest.raises(RuntimeError,match='missing'):
        reel.run(cfg,'Test',[reel.ReelItem('test.dem','a',1,'kills_deaths')],fx={'camera':{'victim':True}})
