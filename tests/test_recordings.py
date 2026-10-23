import json


def test_catalog_survives_restart_dedupes_and_marks_missing(tmp_path, monkeypatch):
    from povforge import recordings
    monkeypatch.setattr(recordings, 'read_duration', lambda p: 20)
    video = tmp_path / 'A.mp4'; video.write_bytes(b'video')
    prefs = {'output': str(tmp_path), 'record_fps': 60, 'minimap': False, 'keyboard': False}
    item = {'result': str(video), 'kind': 'reel', 'name': 'My reel', 'map': 'Dust2',
            'reel': [{'steamid': '1', 'name': 'A', 'mode': 'kill_events'}]}
    store = tmp_path / 'state'
    recordings.remember(store, item, prefs, 80)
    recordings.remember(store, item, prefs, 80)
    rows = recordings.list_videos(store, prefs)['items']
    assert len(rows) == 1
    assert rows[0]['mode'] == 'kill_events'
    assert rows[0]['players'] == ['A']
    assert rows[0]['duration'] == 20 and rows[0]['elapsed'] == 80
    video.unlink()
    assert recordings.list_videos(store, prefs)['items'][0]['missing'] is True


def test_catalog_discovers_old_outputs_without_traversing_work_or_links(tmp_path):
    from povforge import recordings
    root = tmp_path / 'videos'; root.mkdir()
    player = root / 'Alice'; player.mkdir()
    (player / 'old.mp4').write_bytes(b'video')
    work = root / '工作文件'; work.mkdir()
    (work / 'raw.mp4').write_bytes(b'raw')
    custom = tmp_path / 'custom'; custom.mkdir()
    (custom / 'custom.mp4').write_bytes(b'custom')
    store = tmp_path / 'state'; store.mkdir()
    (store / 'recordings.json').write_text('{broken')
    prefs = {'output': str(root), 'player_folders': {'1': {'path': str(custom), 'name': 'A'}}}
    rows = recordings.list_videos(store, prefs)['items']
    assert {r['name'] for r in rows} == {'old', 'custom'}
    assert all(r['duration'] is None for r in rows), 'listing must not probe every video'
    assert recordings.list_videos(store, prefs)['free_bytes'] > 0


def test_failed_recording_never_enters_catalog(tmp_path):
    from povforge import recordings
    recordings.remember(tmp_path, {'result': ''}, {}, 0)
    assert not (tmp_path / 'recordings.json').exists()


def test_malformed_catalog_rows_cannot_break_library(tmp_path):
    from povforge import recordings
    (tmp_path / 'recordings.json').write_text(json.dumps([
        {'path':str(tmp_path/'missing.mp4'),'mtime':'bad','players':False},
        {'path':str(tmp_path/'other.mp4'),'mtime':None,'size':None}, {'path':'\u0000'}]))
    result = recordings.list_videos(tmp_path, {})
    assert isinstance(result['items'],list)


def test_queue_persists_finished_result_and_start_settings_before_clear(tmp_path, monkeypatch):
    from povforge.gui import server
    from povforge import recordings
    from test_gui import FakeJob
    monkeypatch.setenv('POVFORGE_STATE', str(tmp_path/'state'))
    monkeypatch.setattr(recordings,'read_duration',lambda p:20)
    job = FakeJob()
    prefs = {'output':str(tmp_path),'record_fps':60}
    q = server.Queue(job,prefs)
    item = q.add('x.dem','a','Alice',[],'Dust2')
    video = tmp_path/'video.mp4';video.write_bytes(b'video')
    prefs['record_fps'] = 240
    job.snapshot = lambda: {'state':'done','item':item['id'],'result':str(video),
        'highlights':'','cover':'','description':'','title':'','error':'','elapsed':80}
    job.state='done';job.on_finish();q.clear_finished()
    row = recordings.list_videos(server.app_dir(),prefs)['items'][0]
    assert row['players']==['Alice'] and row['profile']['fps']==60


def test_reel_history_searches_real_maps_not_queue_summary(tmp_path,monkeypatch):
    from povforge.gui import server
    from povforge import recordings
    from test_gui import FakeJob
    monkeypatch.setenv('POVFORGE_STATE',str(tmp_path/'state'))
    monkeypatch.setattr(recordings,'read_duration',lambda p:20)
    monkeypatch.setattr(server,'_known_demos',lambda:{'x.dem':{'map':'Dust2'},'y.dem':{'map':'Mirage'}})
    video=tmp_path/'reel.mp4';video.write_bytes(b'video')
    job=FakeJob();prefs={'output':str(tmp_path)};q=server.Queue(job,prefs)
    item=q.add_reel('Custom title',[{'demo':d,'steamid':'a','round':1,'mode':'kills','name':'A'} for d in ['x.dem','y.dem']], 'Reel, 2 rounds')
    job.snapshot=lambda:{'state':'done','item':item['id'],'result':str(video),
        'highlights':'','cover':'','description':'','title':'','error':'','elapsed':80}
    job.state='done';job.on_finish()
    row=recordings.list_videos(server.app_dir(),prefs)['items'][0]
    assert row['maps']==['Dust2','Mirage']
