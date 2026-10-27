from collections import namedtuple


def test_storage_checks_new_folders_without_creating_them(tmp_path):
    from povforge.preflight import storage
    target=tmp_path/'new'/'player'
    rows=storage({'output':target})
    assert rows[0]['state']=='ok' and rows[0]['free_bytes']>0
    assert not target.exists() and list(tmp_path.iterdir())==[]


def test_storage_detects_file_permission_and_low_space(tmp_path,monkeypatch):
    from povforge import preflight
    target=tmp_path/'file';target.write_text('keep')
    assert preflight.storage({'output':target/'child'})[0]['reason']=='not_directory'
    usage=namedtuple('usage','total used free')
    monkeypatch.setattr(preflight.shutil,'disk_usage',lambda p:usage(1024**4,0,100))
    assert preflight.storage({'output':tmp_path})[0]['reason']=='low_space'
    monkeypatch.setattr(preflight,'probe_write',lambda p:(_ for _ in ()).throw(PermissionError()))
    assert preflight.storage({'output':tmp_path})[0]['reason']=='not_writable'
    assert target.read_text()=='keep'


def test_environment_checks_are_readonly_and_actionable():
    from povforge.preflight import environment
    ready={'windows':True,'hlae':'hlae','ffmpeg':'ffmpeg','cs2':'cs2','steam_running':True}
    assert all(r['state']=='ok' for r in environment(ready))
    blocked=environment({**ready,'anticheat':['FACEIT'],'settings_pending':True,'cs2_running':True})
    assert {r['reason'] for r in blocked if r['state']=='error'}=={'anticheat','settings_pending','cs2_running'}

