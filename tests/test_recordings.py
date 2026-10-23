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
