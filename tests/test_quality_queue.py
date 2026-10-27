from types import SimpleNamespace

from povforge.gui.server import Queue
from test_gui import FakeJob


def test_completed_video_checks_before_next_recording_and_respects_saved_choice(monkeypatch,tmp_path):
    from povforge import recordings
    monkeypatch.setattr(recordings,'remember',lambda *a:None)
    calls=[]
    checker=SimpleNamespace(busy=False)
    def submit(path):
        calls.append(path);checker.busy=True
    checker.submit=submit
    job=FakeJob();prefs={'check_video':True}
    queue=Queue(job,prefs,checker=checker)
    queue.add('a.dem','a','A',[],'')
    prefs['check_video']=False
    queue.add('b.dem','b','B',[],'')
    job.finish()
    assert calls==['v.mp4'] and job.started==['A']
    checker.busy=False;queue._start_next()
    assert job.started==['A','B']
    job.finish()
    assert len(calls)==1
