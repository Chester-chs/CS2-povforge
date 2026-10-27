import json
from types import SimpleNamespace

import pytest

from test_gui_security import http_app, session_token


def authorize(authority, request):
    return {'Origin':'http://'+authority,'X-Povforge-Token':session_token(request)}


def test_profiles_api_validates_and_does_not_start_recording(http_app,monkeypatch,tmp_path):
    from povforge.gui import server
    app,output,authority,request=http_app
    monkeypatch.setenv('POVFORGE_STATE',str(tmp_path/'state'))
    app.prefs['record_fps']=120
    headers=authorize(authority,request)
    body={'name':'AWP','mode':'kill_events','weapons':['awp']}
    assert request('/api/profiles/save','POST',{},json.dumps(body))[0]==403
    status,data=request('/api/profiles/save','POST',headers,json.dumps(body))
    assert status==200 and json.loads(data)['record_profiles'][0]['options']['record_fps']==120
    app.prefs['record_fps']=60
    status,data=request('/api/profiles/apply','POST',headers,json.dumps({'name':'AWP'}))
    assert status==200 and json.loads(data)['prefs']['record_fps']==120
    assert app.prefs['output']==str(output)
    assert request('/api/profiles/save','POST',headers,json.dumps({**body,'mode':'bad'}))[0]==400
    assert request('/api/profiles/remove','POST',headers,json.dumps({'name':'AWP'}))[0]==200
    assert app.prefs['record_profiles']==[]


def test_preflight_uses_configured_destinations_and_does_not_mutate_prefs(http_app,monkeypatch,tmp_path):
    from povforge.gui import server
    app,output,authority,request=http_app
    app.prefs.update(by_player=True,player_folders={'a':{'folder':'Player','name':'Player','path':str(tmp_path/'custom')}})
    app.setup=SimpleNamespace(status=lambda:{'windows':True,'cs2':True,'hlae':True,'ffmpeg':True,'steam_running':True})
    before=json.dumps(app.prefs)
    monkeypatch.setattr(server,'save_prefs',lambda p:pytest.fail('preflight may not save prefs'))
    headers=authorize(authority,request)
    status,data=request('/api/preflight','POST',headers,json.dumps({'kind':'match','steamid':'a','name':'Player','output':'attacker'}))
    data=json.loads(data)
    assert status==200 and data['ok']
    assert {r['key'] for r in data['checks']} >= {'output','work','destination','ffmpeg'}
    assert before==json.dumps(app.prefs) and not (tmp_path/'custom').exists()
    assert request('/api/preflight','POST',{},'{}')[0]==403


def test_diagnostics_export_cancel_and_untrusted_path(http_app,monkeypatch,tmp_path):
    from povforge.gui import server
    app,_,authority,request=http_app
    app.setup=SimpleNamespace(status=lambda:{'ffmpeg':'private'})
    app.job=SimpleNamespace(snapshot=lambda:{'state':'error','error':'api_key=secret','lines':[]})
    headers=authorize(authority,request)
    monkeypatch.setattr(server,'pick_folder',lambda p:None)
    assert request('/api/diagnostics/export','POST',headers,'{}')==(200,b'{"cancelled": true}')
    destination=tmp_path/'chosen';destination.mkdir()
    monkeypatch.setattr(server,'pick_folder',lambda p:str(destination))
    status,data=request('/api/diagnostics/export','POST',headers,json.dumps({'path':str(tmp_path/'injected')}))
    assert status==200 and len(list(destination.glob('*.json')))==1
    assert not (tmp_path/'injected').exists()
    assert 'api_key' not in next(destination.glob('*.json')).read_text()
    assert request('/api/diagnostics/export','POST',{},'{}')[0]==403


def test_quality_requests_allow_only_catalog_movies_and_never_probe_on_listing(http_app,monkeypatch,tmp_path):
    from povforge.gui import server
    app,output,authority,request=http_app
    monkeypatch.setenv('POVFORGE_STATE',str(tmp_path/'state'))
    calls=[]
    app.checker=SimpleNamespace(submit=lambda p:calls.append(str(p)) or True,status=lambda p:None,busy=False)
    app.job=SimpleNamespace(busy=False)
    app.queue=SimpleNamespace(lock=__import__('threading').Lock(),items=[])
    video=output/'clip.mp4';video.write_bytes(b'not decoded by list')
    headers=authorize(authority,request)
    assert request('/api/library')[0]==200 and calls==[]
    assert request('/api/library/check','POST',headers,json.dumps({'path':str(tmp_path/'outside.mp4')}))[0]==404
    assert request('/api/library/check','POST',headers,json.dumps({'path':str(video)}))[0]==200
    assert calls==[str(video.resolve())]
    app.job.busy=True
    assert request('/api/library/check','POST',headers,json.dumps({'path':str(video)}))[0]==409
    assert request('/api/library/check','POST',{},'{}')[0]==403


def test_preflight_does_not_block_queueing_behind_owned_running_game(http_app):
    app,_,authority,request=http_app
    app.job=SimpleNamespace(busy=True)
    app.setup=SimpleNamespace(status=lambda:{'windows':True,'cs2':True,'hlae':True,'ffmpeg':True,
        'steam_running':True,'cs2_running':True,'settings_pending':True})
    headers=authorize(authority,request)
    status,data=request('/api/preflight','POST',headers,'{}')
    assert status==200 and json.loads(data)['ok'], 'Current task owns these temporary recording conditions'


def test_preflight_rejects_malformed_reel_before_storage_probe(http_app):
    app,_,authority,request=http_app
    headers=authorize(authority,request)
    for items in ({'steamid':'a'},['not a row'],[{'name':'missing id'}]):
        assert request('/api/preflight','POST',headers,json.dumps({'kind':'reel','items':items}))[0]==400
