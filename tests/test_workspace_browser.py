"""Render the real frontend against an isolated fake API; never starts the app/game."""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from povforge import cdp
from povforge.gui.server import STATIC, CONTENT_TYPES


@pytest.fixture
def workspace_site():
    state = {
        'version': '0.15.1', 'prefs': {'folders_set': True, 'lang': 'zh', 'appearance': 'light',
                                    'accent': 'purple', 'demo_folders': ['C:/Demos'], 'output': 'C:/Videos'},
        'setup': {'windows': True, 'cs2': True, 'hlae': True, 'ffmpeg': True, 'anticheat': [], 'problems': []},
        'job': {'state': 'idle', 'lines': [], 'recorded': [], 'planned': [], 'step': [0, 0]},
        'queue': {'items': [], 'paused': False}, 'update': None, 'screen': [1920, 1080], 'sizes': ['1080'],
    }
    demos = [{'path': f'C:/Demos/match-{i}.dem', 'name': f'faceit-match-{i}-example.dem.zst',
              'map': name, 'score': score, 'faceit': True, 'mtime': 1792600000-i*86400,
              'size': mb*1024*1024, 'cached': i != 3}
             for i, (name, score, mb) in enumerate([('Dust2','13:0',101), ('Dust2','16:14',381),
                                                    ('Cache','10:13',179), ('Ancient','13:8',445), ('Nuke','13:16',296)])]
    player = {'steamid': 'a', 'name': 'Example player', 'k': 4, 'd': 1, 'a': 1, 'adr': 90, 'hs': 50,
              'rounds_k': [3, 1], 'rounds_event_k': [3, 1], 'rounds_died': [False, True],
              'rounds_hs': [1, 1], 'rounds_clutch': [0, 0], 'rounds_won': [True, False]}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, data, content='application/json', status=200):
            body = data if isinstance(data, bytes) else json.dumps(data).encode()
            self.send_response(status)
            self.send_header('Content-Type', content)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == '/':
                return self.respond((STATIC / 'index.html').read_bytes(), 'text/html; charset=utf-8')
            if self.path.startswith('/static/'):
                f = (STATIC / self.path[len('/static/'):]).resolve()
                if STATIC.resolve() in f.parents and f.is_file():
                    return self.respond(f.read_bytes(), CONTENT_TYPES.get(f.suffix, 'application/octet-stream'))
            if self.path == '/api/state':
                return self.respond(state)
            if self.path == '/api/demos':
                return self.respond(demos)
            if self.path == '/api/library':
                return self.respond({'items': [{'path':'C:/Videos/A.mp4','name':'Example clip','players':['Example player'],
                    'maps':['Dust2'],'mode':'kill_events','size':1024,'mtime':1792600000,'duration':20,'missing':False}], 'free_bytes':1000000000})
            if self.path == '/api/map-thumbnail?map=de_dust2':
                return self.respond((STATIC / 'icon.png').read_bytes(), 'image/png')
            if self.path == '/api/workfiles':
                return self.respond({'bytes': 0, 'path': 'C:/Fake-work'})
            self.respond({}, status=404)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            if self.path == '/api/inspect':
                return self.respond({'path': body['path'], 'name': 'match.dem', 'map': 'de_dust2',
                                     'map_pretty': 'Dust2', 'rounds': 2, 'minutes': 3,
                                     'recording_details': {'version':1,'seconds':{'a':[25,18]},
                                         'rounds':[{'number':1,'start':0,'end':30},{'number':2,'start':0,'end':30}],
                                         'events':[{'round':1,'tick':100,'time':10,'attacker':'a','victim':'b','weapon':'ak47','headshot':True,'pov':True},
                                                   {'round':1,'tick':150,'time':15,'attacker':'a','victim':'c','weapon':'m4a1','headshot':False,'pov':True}]}, 'teams': [
                                         {'name': 'Team A', 'score': 1, 'players': [player]},
                                         {'name': 'Team B', 'score': 1, 'players': []}], 'duels': []})
            if self.path == '/api/folders/confirm':
                state['prefs']['folders_set'] = True
                return self.respond(state['prefs'])
            if self.path == '/api/prefs':
                state['prefs'].update(body)
                return self.respond(state['prefs'])
            self.respond({})

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f'http://127.0.0.1:{server.server_port}/', state
    server.shutdown()
    server.server_close()


@pytest.mark.skipif(cdp.find_browser() is None, reason='Edge/Chrome required')
def test_per_kill_replay_choices_reach_event_and_duel_requests(workspace_site):
    url, _ = workspace_site
    with cdp.Browser(size=(1920, 1080)) as browser:
        page = browser.page()
        try:
            page.call('Page.enable')
            page.call('Page.navigate', url=url)
            assert page.wait_for("document.querySelectorAll('.demo-card').length === 5", 15)
            page.evaluate("""window.app = Alpine.$data(document.body);
              app.reelOpen=true;app.libraryOpen=false;app.reel.content='kill_events';
              app.reel.title='Test'; app.reel.steamid='11';
              app.reel.sources=[{path:'C:/Demos/match.dem.zst', info:{map_pretty:'Dust2',teams:[
                {players:[{steamid:'11',name:'Attacker'}]}, {players:[{steamid:'33',name:'Victim'}]}],
                duels:[{round:1,tick:100,attacker:'11',victim:'33'},
                       {round:1,tick:200,attacker:'11',victim:'33'},
                       {round:1,tick:300,attacker:'33',victim:'11'}]}}];
              app.reel.items=[{path:'C:/Demos/match.dem.zst',steamid:'11',round:1,mode:'kill_events',key:'one',name:'Attacker'}];
              app.fx={transition:'flash',intro:'title',pace:'tight',kill_slowmo:true,
                      camera:app.cameraSettings({victim:true})};
              app.post=async (url,body)=>{window.sent={url,body};return {queue:{items:[]},state:'idle'}};
              app.toast=()=>{};""")
            assert page.wait_for("document.querySelectorAll('.victim-list input').length===2", 3)
            page.evaluate("document.querySelector('.victim-list input').click()")
            assert page.evaluate("Array.from(document.querySelectorAll('.victim-list input'),n=>n.checked)") == [False, True]
            page.evaluate("app.startReel(false)", await_promise=True)
            sent = page.evaluate('window.sent')
            fx = sent['body']['effects']
            assert fx['camera']['victim'] is True
            assert fx['camera']['placement'] == 'after_kill'
            assert fx['camera']['selected'] == ['["c:/demos/match.dem.zst","11",200,"33"]']
            assert fx.get('transition', 'cut') == 'cut'
            assert not fx.get('kill_slowmo') and fx.get('pace', 'normal') == 'normal'
            page.evaluate("app.reel.content='duel';app.reel.items[0].opponent='33';app.selectAllVictims(true)")
            assert page.wait_for("document.querySelector('.camera-options') === null", 3)
            page.evaluate("app.startReel(false)", await_promise=True)
            assert page.evaluate('window.sent.body.effects.camera.victim') is False
            assert page.evaluate('app.fx.camera.victim') is True
            page.evaluate("app.reel.content='kill_events'")
            assert page.wait_for("document.querySelectorAll('.victim-list input').length===2", 3)
            page.evaluate("app.selectAllVictims(false)")
            assert page.evaluate('JSON.stringify(app.fx.camera.selected)') == '[]'
        finally:
            page.close()


@pytest.mark.skipif(cdp.find_browser() is None, reason='Edge/Chrome required')
def test_workspace_setup_match_reel_search_and_layout(workspace_site):
    url, state = workspace_site
    with cdp.Browser(size=(1264, 812)) as browser:
        page = browser.page()
        try:
            page.call('Page.enable')
            page.call('Emulation.setDeviceMetricsOverride', width=1264, height=812, deviceScaleFactor=1, mobile=False)
            page.call('Page.addScriptToEvaluateOnNewDocument', source="window.uiErrors=[];window.addEventListener('error',e=>uiErrors.push(e.message));")
            page.call('Page.navigate', url=url)
            assert page.wait_for("document.querySelectorAll('.demo-card').length === 5", 15)
            page.evaluate("window.visible=s=>!!document.querySelector(s)?.getBoundingClientRect().height")
            assert page.evaluate("visible('.library') && !visible('.setup-continue')")
            assert page.evaluate("document.querySelector('.sidebar .demo-card') === null")
            assert page.evaluate("document.querySelector('.sidebar .app-head') === null")
            assert page.evaluate("document.querySelector('#record-resolution') === null")
            assert page.evaluate("document.querySelector('.fixed-resolution').textContent") == '1080P'
            assert page.evaluate("Array.from(document.querySelectorAll('select#record-fps option'), o=>o.value)") == ['24','30','60','120','144','240']
            page.evaluate("let rate=document.querySelector('#record-fps');rate.value='144';rate.dispatchEvent(new Event('change',{bubbles:true}))")
            page.evaluate("Alpine.$data(document.body).savePrefs()", await_promise=True)
            assert state['prefs']['record_fps'] == 144
            assert page.evaluate("document.querySelector('.demo-card').getBoundingClientRect().width > 750")
            assert page.evaluate("Array.from(document.querySelectorAll('.modes button'),b=>b.textContent.trim())") == ['Demo整场录制', 'Demo击杀视角', 'Demo击杀和死亡视角', '双人对位数据', '高光集锦']
            assert page.evaluate("document.querySelector('.library h1').textContent") == 'Demo整场录制'
            assert page.evaluate("document.querySelector('.library-head > button').textContent.trim()") == '上传 Demo'
            page.call('Emulation.setDeviceMetricsOverride', width=1920, height=1080, deviceScaleFactor=1, mobile=False)
            assert page.wait_for("document.querySelector('.recording-panel').getBoundingClientRect().left >= document.querySelector('.library').getBoundingClientRect().right", 3)
            assert page.evaluate("Math.abs(document.querySelector('.recording-panel').getBoundingClientRect().top - document.querySelector('.library').getBoundingClientRect().top) < 12")
            assert page.evaluate("document.querySelector('.content').scrollWidth <= document.querySelector('.content').clientWidth")
            page.call('Emulation.setDeviceMetricsOverride', width=1264, height=812, deviceScaleFactor=1, mobile=False)
            screenshots = os.environ.get('POVFORGE_UI_SHOTS')

            def shot(name):
                if screenshots:
                    folder = Path(screenshots)
                    folder.mkdir(parents=True, exist_ok=True)
                    page.screenshot(folder / name)

            shot('workspace-light.png')
            page.evaluate("const input=document.querySelector('input[type=search]');input.value='nuke';input.dispatchEvent(new Event('input',{bubbles:true}))")
            assert page.wait_for("document.querySelectorAll('.demo-card').length === 1", 3)
            page.call('Emulation.setDeviceMetricsOverride', width=1264, height=400, deviceScaleFactor=1, mobile=False)
            assert page.wait_for("document.querySelector('.content').scrollHeight > document.querySelector('.content').clientHeight", 3)
            page.evaluate("document.querySelector('.content').scrollTop = document.querySelector('.content').scrollHeight")
            page.evaluate("document.querySelector('.demo-card').click()")
            assert page.wait_for("visible('.match')", 5)
            page.evaluate("document.querySelector('.players tbody tr').click()")
            assert page.wait_for("document.querySelector('.match-totals')?.textContent.includes('4')", 3)
            assert page.evaluate("document.querySelector('.output-root button') !== null && document.querySelector('.folder-name') === null")
            assert page.wait_for("document.querySelector('.content').scrollTop === 0", 3)
            assert page.wait_for("document.querySelector('.map-scene').naturalWidth > 0", 5)
            assert '/api/map-thumbnail?map=de_dust2' in page.evaluate("document.querySelector('.map-scene').src")
            page.evaluate("Alpine.$data(document.body).demo.map = 'missing_map'")
            assert page.wait_for("document.querySelector('.map-scene').style.visibility === 'hidden'", 3)
            page.evaluate("Alpine.$data(document.body).demo.map = 'de_dust2'")
            assert page.wait_for("document.querySelector('.map-scene').naturalWidth > 0 && document.querySelector('.map-scene').style.visibility === 'visible'", 3)
            page.evaluate("document.querySelector('.match .back-library').click()")
            assert page.wait_for("visible('.library')", 3)
            page.evaluate("document.querySelectorAll('.modes button')[4].click()")
            page.evaluate("document.querySelector('.demo-card').click()")
            assert page.wait_for("!document.querySelector('.library-bottom button').disabled", 3)
            page.evaluate("document.querySelector('.content').scrollTop = document.querySelector('.content').scrollHeight")
            assert page.evaluate("document.querySelector('.content').scrollTop > 0")
            page.evaluate("document.querySelector('.library-bottom button').click()")
            assert page.wait_for("visible('.reel')", 5)
            assert page.wait_for("document.querySelector('.content').scrollTop === 0", 3)
            page.evaluate("Alpine.$data(document.body).fx = { ...Alpine.$data(document.body).fx, camera:{mode:'pov',victim:false} }")
            assert page.wait_for("document.querySelector('.camera-options .group')?.getBoundingClientRect().height > 0", 3)
            assert page.evaluate("document.querySelector('.camera-options .group + .hint').getBoundingClientRect().top - document.querySelector('.camera-options .group').getBoundingClientRect().bottom >= 10")
            page.call('Emulation.setDeviceMetricsOverride', width=1920, height=1080, deviceScaleFactor=1, mobile=False)
            assert page.wait_for("document.querySelector('.reel').getBoundingClientRect().width > 900", 3)
            assert page.evaluate("document.querySelector('.recording-panel').getBoundingClientRect().left >= document.querySelector('.reel').getBoundingClientRect().right")
            assert page.evaluate("document.querySelectorAll('.reel option[value=kill_events]').length === 0")
            for index, title, mode in [(1, 'Demo击杀视角', 'kill_events'), (2, 'Demo击杀和死亡视角', 'kills_deaths'), (3, '双人对位数据', 'duel'), (4, '高光集锦', 'kills')]:
                page.evaluate("document.querySelector('.content').scrollTop = document.querySelector('.content').scrollHeight")
                page.evaluate(f"document.querySelectorAll('.modes button')[{index}].click()")
                assert page.wait_for(f"document.querySelector('.reel h1').textContent === '{title}'", 3)
                assert page.wait_for("document.querySelector('.content').scrollTop === 0", 3)
                assert page.evaluate('Alpine.$data(document.body).reel.content') == mode
                expected = 'true' if mode == 'kills' else 'false'
                assert page.wait_for(f"!!document.querySelector('.reel-style')?.getBoundingClientRect().height === {expected}", 3)
                if mode == 'duel':
                    assert page.wait_for("document.querySelector('.camera-options') === null", 3)
                else:
                    assert page.wait_for("document.querySelector('.camera-options input.switch') !== null", 3)
                    assert page.evaluate("!document.querySelector('.camera-options input.switch').disabled")
                    assert page.evaluate("document.querySelector('.camera-options .row-main b').textContent") == '受害者视角'
            page.call('Emulation.setDeviceMetricsOverride', width=1264, height=812, deviceScaleFactor=1, mobile=False)
            page.evaluate("document.querySelector('.reel .back-library').click()")
            assert page.wait_for("visible('.library') && document.querySelector('.demo-card.selected')", 3)
            page.evaluate("document.documentElement.dataset.theme='dark'")
            shot('workspace-dark.png')
            page.call('Emulation.setDeviceMetricsOverride', width=390, height=844, deviceScaleFactor=1, mobile=False)
            assert page.wait_for("document.documentElement.scrollWidth <= 390", 3)
            shot('workspace-narrow.png')
            assert page.evaluate('uiErrors') == []

            state['prefs']['folders_set'] = False
            page.call('Emulation.setDeviceMetricsOverride', width=1264, height=812, deviceScaleFactor=1, mobile=False)
            page.call('Page.navigate', url=url)
            # Navigation can return before Alpine has bound the new document.
            # A visible uninitialized element is not yet a clickable control.
            assert page.wait_for("Alpine.$data(document.body).prefs.demo_folders?.[0] === 'C:/Demos' && document.querySelector('.folders .primary')?.textContent === '就用这两个' && document.querySelector('.setup-continue')?.getBoundingClientRect().height > 0", 10)
            shot('workspace-setup.png')
            page.evaluate("document.querySelector('.folders .primary').click()")
            assert page.wait_for("Alpine.$data(document.body).prefs.folders_set", 3)
            page.evaluate("document.querySelector('.setup-continue button').click()")
            assert page.wait_for("document.querySelector('.library').getBoundingClientRect().height > 0", 3)
            assert page.evaluate('uiErrors') == []
            page.evaluate("document.querySelector('.side-foot .icon-btn').click()")
            assert page.wait_for("document.querySelector('.settings-page')?.getBoundingClientRect().height > 0", 3)
            assert page.evaluate("document.querySelector('.settings-page #by-player') === null && document.querySelector('.recording-panel #by-player') !== null")
            page.evaluate("let font=document.querySelector('#app-font');font.value='yahei';font.dispatchEvent(new Event('change',{bubbles:true}))")
            assert page.wait_for("document.documentElement.dataset.font === 'yahei'", 3)
            page.evaluate("let radius=document.querySelector('#popup-radius');radius.value='24';radius.dispatchEvent(new Event('input',{bubbles:true}));radius.dispatchEvent(new Event('change',{bubbles:true}))")
            assert page.wait_for("getComputedStyle(document.querySelector('.popup-preview')).borderRadius === '24px'", 3)
            shot('settings-appearance.png')
            page.call('Emulation.setDeviceMetricsOverride', width=390, height=844, deviceScaleFactor=1, mobile=False)
            assert page.wait_for("document.documentElement.scrollWidth <= 390", 3)
            shot('settings-narrow.png')
            page.call('Emulation.setDeviceMetricsOverride', width=1264, height=812, deviceScaleFactor=1, mobile=False)
            page.evaluate("document.querySelector('[data-settings-tab=about]').click()")
            assert page.wait_for("document.querySelector('.about-page')?.getBoundingClientRect().height > 0", 3)
            shot('settings-about.png')
            page.call('Page.navigate', url=url)
            assert page.wait_for("document.documentElement.dataset.font === 'yahei'", 5)
            assert page.evaluate("getComputedStyle(document.querySelector('.popup-preview')).borderRadius") == '24px'
            assert page.evaluate('uiErrors') == []
        finally:
            page.close()
