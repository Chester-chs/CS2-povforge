import json

from povforge.gui.server import Queue
from test_gui import FakeJob


class SavedJob(FakeJob):
    def start(self,item,prefs):
        self.prefs=prefs
        super().start(item,prefs)


def test_restart_restores_tasks_paused_without_starting_recording(tmp_path):
    store = tmp_path/'queue.json'
    job = FakeJob(); prefs = {'record_fps':120,'output':str(tmp_path),'minimap':True}
    queue = Queue(job,prefs,store=store)
    queue.add('a.dem','1','Alice',[1,3],'Dust2')
    queue.add_reel('AWP clips',[{'demo':'a.dem','steamid':'1','round':3,'mode':'kill_events'}],fx={'music_volume':.3})
    restarted = SavedJob(); restored = Queue(restarted,{'record_fps':60},store=store)
    assert restarted.started == []
    snap = restored.snapshot()
    assert snap['paused'] and snap['recovered']
    assert [i['state'] for i in snap['items']] == ['queued','queued']
    assert snap['items'][1]['reel'][0]['mode'] == 'kill_events'
    restored.resume()
    assert restarted.started == ['Alice']
    assert restarted.last['rounds'] == [1,3]
    assert restarted.prefs['record_fps'] == 120
    restarted.finish()
    assert restarted.started == ['Alice','AWP clips']


def test_remove_clear_and_retry_changes_survive_restart(tmp_path):
    store=tmp_path/'queue.json'; job=FakeJob(); queue=Queue(job,{},store=store)
    queue.add('x.dem','1','A',[],''); queue.add('x.dem','2','B',[],'')
    job.finish('cancelled'); queue.remove(2)
    queue.clear_finished()
    restored=Queue(FakeJob(),{},store=store)
    assert restored.snapshot()['items']==[]
    item=restored.add('x.dem','3','C',[],'')
    restored.job.finish('error'); restored.retry(item['id'])
    assert Queue(FakeJob(),{},store=store).snapshot()['items'][0]['state']=='queued'


def test_corrupt_store_is_reported_and_never_launches(tmp_path):
    store=tmp_path/'queue.json'; store.write_text('{broken')
    job=FakeJob(); queue=Queue(job,{},store=store)
    assert job.started==[] and queue.snapshot()['items']==[]
    assert queue.snapshot()['save_error']
    assert store.read_text()=='{broken'


def test_unknown_schema_or_invalid_task_cannot_restore_executable_fields(tmp_path):
    store=tmp_path/'queue.json'
    for payload in [{'version':99,'items':[]}, {'version':1,'items':[{'id':1,'kind':'shell','command':'bad'}]}]:
        store.write_text(json.dumps(payload)); job=FakeJob(); queue=Queue(job,{},store=store)
        assert job.started==[] and queue.snapshot()['items']==[]
        assert queue.snapshot()['save_error']


def test_failed_atomic_save_keeps_previous_snapshot(tmp_path,monkeypatch):
    store=tmp_path/'queue.json'; queue=Queue(FakeJob(),{},store=store)
    queue.add('x.dem','1','A',[],''); original=store.read_bytes()
    from pathlib import Path
    replace=Path.replace
    def fail_replace(path,target):
        if Path(target)==store: raise OSError('disk full')
        return replace(path,target)
    monkeypatch.setattr(Path,'replace',fail_replace)
    queue.add('x.dem','2','B',[],'')
    assert store.read_bytes()==original
    assert queue.snapshot()['save_error']


def test_removing_all_recovered_tasks_clears_recovery_notice(tmp_path):
    store=tmp_path/'queue.json';first=Queue(FakeJob(),{},store=store)
    first.add('x.dem','1','A',[],'')
    restored=Queue(FakeJob(),{},store=store);restored.remove(1)
    assert not restored.snapshot()['recovered']
    restored.add('x.dem','2','B',[],'')
    assert restored.job.started==['B']


def test_restored_settings_do_not_replace_current_app_preferences(tmp_path,monkeypatch):
    from povforge.gui import server
    monkeypatch.setenv('POVFORGE_STATE',str(tmp_path/'state'))
    prefs=server.load_prefs();prefs['output']=str(tmp_path/'videos');prefs['record_fps']=120
    store=tmp_path/'queue.json';first=Queue(FakeJob(),prefs,store=store)
    first.add('x.dem','1','A',[],'');prefs['record_fps']=60;server.save_prefs(prefs)
    captured={};original=server.write_job_config
    def config(settings,videos):
        captured.update(settings);return original(settings,videos)
    monkeypatch.setattr(server,'write_job_config',config)
    def fail(*a,**kw):raise OSError('isolated test: no game process')
    monkeypatch.setattr(server.subprocess,'Popen',fail)
    restored=Queue(server.Job(),prefs,store=store);restored.resume()
    assert captured['record_fps']==120
    assert server.load_prefs()['record_fps']==60
    assert restored.snapshot()['items'][0]['state']=='error'
