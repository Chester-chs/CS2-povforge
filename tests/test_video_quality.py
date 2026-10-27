import json
import subprocess
import threading

import pytest


def test_metadata_rejects_missing_video_and_marks_missing_audio():
    from povforge import video_quality as quality
    with pytest.raises(ValueError): quality.metadata({'streams':[{'codec_type':'audio'}]})
    info=quality.metadata({'format':{'duration':'30'},'streams':[{'codec_type':'video','width':1920,
        'height':1080,'avg_frame_rate':'60/1'}]})
    assert info['duration']==30 and info['fps']==60 and not info['audio']


def test_detection_offsets_and_merges_duplicate_sample_findings():
    from povforge import video_quality as quality
    text='black_start:1 black_end:4 black_duration:3\nfreeze_start: 5\nfreeze_end: 9 | freeze_duration: 4'
    issues=quality.detections(text,20,15)
    assert [(r['kind'],r['at'],r['end']) for r in issues]==[('black',21,24),('freeze',25,29)]
    assert quality.sample_windows(10)==[(0,10)]
    windows=quality.sample_windows(600)
    assert len(windows)==3 and sum(span for _,span in windows)==45


def test_cached_reports_expire_when_video_changes(tmp_path):
    from povforge import video_quality as quality
    video=tmp_path/'clip.mp4';video.write_bytes(b'original')
    report={'state':'warning','issues':[{'kind':'black','at':1,'end':4}],'sampled':True}
    quality.save(tmp_path,video,report)
    assert quality.read(tmp_path,video)['issues'][0]['at']==1
    video.write_bytes(b'changed')
    assert quality.read(tmp_path,video) is None


def test_manager_serializes_checks_and_notifies_queue(tmp_path,monkeypatch):
    from povforge import video_quality as quality
    entered=threading.Event();release=threading.Event();finished=threading.Event()
    video=tmp_path/'clip.mp4';video.write_bytes(b'x')
    def check(*args,**kw):
        entered.set();assert release.wait(3)
        return {'state':'ok','issues':[]}
    monkeypatch.setattr(quality,'check',check)
    manager=quality.Manager(tmp_path,on_idle=finished.set)
    try:
        assert manager.submit(video)
        assert entered.wait(3) and manager.busy
        assert not manager.submit(video)
        release.set();assert finished.wait(3)
        assert not manager.busy and quality.read(tmp_path,video)['state']=='ok'
    finally:
        release.set();manager.close()


def test_real_ffmpeg_sample_finds_black_and_freeze_without_game(tmp_path):
    from povforge import video_quality as quality
    from povforge.tools import find_ffmpeg
    ffmpeg=find_ffmpeg()
    if not ffmpeg: pytest.skip('FFmpeg required')
    video=tmp_path/'black.mp4'
    subprocess.run([ffmpeg,'-nostdin','-v','error','-f','lavfi','-i','color=c=black:s=160x90:r=10:d=5',
                    '-c:v','libx264','-pix_fmt','yuv420p',str(video)],check=True,capture_output=True,timeout=20)
    report=quality.check(video,ffmpeg=ffmpeg)
    assert report['state']=='warning' and report['duration']>=4.9
    assert {'black','freeze','no_audio'} <= {r['kind'] for r in report['issues']}

