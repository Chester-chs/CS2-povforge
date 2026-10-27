"""Automatic recording of downloaded official-matchmaking demos, without Steam or CS2."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from povforge import auto_mm
from povforge import cdp
from test_workspace_browser import workspace_site  # noqa: F401

ME = '76561198000000001'


def info(path, rounds_k=(3, 0, 1, 4), clutch=(0, 1, 0, 0), died=(False, True, False, False), me=ME):
    player = {'steamid': me, 'name': 'Chester', 'rounds_k': list(rounds_k), 'rounds_event_k': list(rounds_k),
              'rounds_hs': [1, 0, 0, 2], 'rounds_clutch': list(clutch), 'rounds_died': list(died)}
    return {'path': path, 'map_pretty': 'Mirage', 'teams': [{'players': [player]}, {'players': [{'steamid': '76561198000000002', 'name': 'Other'}]}]}


class FakeQueue:
    def __init__(self):
        self.reels, self.matches = [], []

    def add_reel(self, title, items, summary='', fx=None):
        self.reels.append({'title': title, 'items': items, 'summary': summary, 'fx': fx})

    def add(self, path, steamid, name, rounds, map_pretty):
        self.matches.append((path, steamid, name, rounds, map_pretty))


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def make(tmp_path, *, busy='', inspect=None, accounts=None, prefs=None):
    replays = tmp_path / 'replays'
    replays.mkdir(exist_ok=True)
    queue, calls, saved = FakeQueue(), [], []
    state = {'busy': busy}
    clock = Clock(1_800_000_000.0)

    def do_inspect(path):
        calls.append(path)
        return (inspect or info)(path)
    w = auto_mm.Watcher(prefs if prefs is not None else {'lang': 'zh'}, tmp_path / 'state', inspect=do_inspect, queue=queue,
                        game_busy=lambda: state['busy'], save_prefs=saved.append,
                        folder_finder=lambda: replays,
                        accounts_finder=lambda: [{'steamid': ME, 'name': 'Chester', 'recent': True}] if accounts is None else accounts,
                        clock=clock)
    return w, replays, queue, calls, state, clock


def write(path, data=b'x' * 100, at=1_800_000_100.0):
    path.write_bytes(data)
    os.utime(path, (at, at))
    return path


def test_steam_accounts_and_replays_folder(tmp_path):
    (tmp_path / 'config').mkdir()
    (tmp_path / 'config' / 'loginusers.vdf').write_text('''"users"
{
  "76561198000000009" { "AccountName" "old" "PersonaName" "Old one" "MostRecent" "0" "Timestamp" "100" }
  "76561198000000001" { "AccountName" "me" "PersonaName" "Chester" "MostRecent" "1" "Timestamp" "50" }
  "bad" { "PersonaName" "x" }
}''', encoding='utf-8')
    accounts = auto_mm.steam_accounts(tmp_path)
    assert [a['steamid'] for a in accounts] == [ME, '76561198000000009']
    assert accounts[0]['name'] == 'Chester'
    assert auto_mm.steam_accounts(tmp_path / 'missing') == []
    exe = Path('D:/SteamLibrary/steamapps/common/Counter-Strike Global Offensive/game/bin/win64/cs2.exe')
    assert auto_mm.replays_folder(exe) == Path('D:/SteamLibrary/steamapps/common/Counter-Strike Global Offensive/game/csgo/replays')


def test_round_choice_matches_the_editor():
    player = info('x')['teams'][0]['players'][0]
    assert auto_mm.plan_rounds(player, 'kills') == [2, 1, 4], 'clutch and 3k+ rounds, best last'
    assert auto_mm.plan_rounds(player, 'kill_events') == [1, 3, 4]
    assert auto_mm.plan_rounds(player, 'kills_deaths') == [1, 2, 3, 4]
    quiet = {'rounds_k': [1, 0, 2], 'rounds_hs': [0, 0, 1], 'rounds_clutch': [0, 0, 0]}
    assert auto_mm.plan_rounds(quiet, 'kills') == [1, 3], 'a quiet match still gets its kills'
    assert auto_mm.plan_rounds({'rounds_k': [0, 0]}, 'kills') == []


def test_only_new_complete_downloads_after_cs2_closes_are_queued(tmp_path):
    w, replays, queue, calls, state, clock = make(tmp_path)
    write(replays / 'match730_old.dem', at=1_799_000_000.0)
    w.configure({'enabled': True})
    assert w.prefs['auto_mm'] and w.prefs['auto_mm_since'] == clock.t and w.prefs['auto_mm_mode'] == 'kills'
    clock.t += 60
    demo = write(replays / 'match730_new.dem', at=clock.t - 1)
    w.tick()
    assert calls == [], 'first sight: the file may still be downloading'
    write(demo, b'x' * 200, at=clock.t)
    clock.t += 5
    w.tick()
    assert calls == [], 'it changed since the last look'
    state['busy'] = 'cs2'
    clock.t += 5
    w.tick()
    assert calls == [] and w.waiting == 'cs2', "the user's own game is never closed; we wait"
    assert w.status()['waiting'] == 'cs2'
    state['busy'] = ''
    w.tick()
    assert calls == [str(demo)]
    assert len(queue.reels) == 1
    reel = queue.reels[0]
    assert reel['title'] == 'Chester 官匹高光集锦 · Mirage'
    assert [i['round'] for i in reel['items']] == [2, 1, 4]
    assert {i['steamid'] for i in reel['items']} == {ME} and {i['mode'] for i in reel['items']} == {'kills'}
    w.tick()
    assert len(calls) == 1, 'each match is handled once'
    recent = w.status()['recent']
    assert [r['state'] for r in recent] == ['queued'] and 'old' not in json.dumps(recent)
    again = auto_mm.Watcher(w.prefs, tmp_path / 'state', inspect=lambda p: info(p), queue=FakeQueue(),
                            game_busy=lambda: '', folder_finder=lambda: replays, accounts_finder=lambda: [], clock=clock)
    again.tick(); again.tick()
    assert again.queue.reels == [], 'handled matches are remembered across restarts'


def test_archive_and_unpacked_copy_are_one_match_and_dem_is_preferred(tmp_path):
    w, replays, queue, calls, state, clock = make(tmp_path)
    w.configure({'enabled': True})
    clock.t += 60
    write(replays / 'match730_a.dem.bz2', at=clock.t - 10)
    write(replays / 'match730_a.dem', at=clock.t - 10)
    w.tick(); w.tick()
    assert calls == [str(replays / 'match730_a.dem')]


def test_modes_failures_and_skips_are_reported_without_retry_loops(tmp_path):
    w, replays, queue, calls, state, clock = make(tmp_path, prefs={'lang': 'en'})
    w.configure({'enabled': True, 'mode': 'match'})
    clock.t += 60
    write(replays / 'one.dem', at=clock.t - 10)
    w.tick(); w.tick()
    assert queue.matches == [(str(replays / 'one.dem'), ME, 'Chester', [], 'Mirage')]

    def broken(path):
        raise RuntimeError('bad demo')
    w.inspect = broken
    write(replays / 'two.dem', at=clock.t - 5)
    w.tick(); w.tick(); w.tick()
    rows = {r['name']: r for r in w.status()['recent']}
    assert rows['two.dem']['state'] == 'error' and 'bad demo' in rows['two.dem']['message']

    w.inspect = lambda p: info(p, me='76561198000000099')
    write(replays / 'three.dem', at=clock.t - 4)
    w.tick(); w.tick()
    rows = {r['name']: r for r in w.status()['recent']}
    assert rows['three.dem']['state'] == 'skipped' and 'not in this match' in rows['three.dem']['message']

    w.configure({'mode': 'kills_deaths', 'steamid': ''})
    w.inspect = lambda p: info(p, rounds_k=(0, 0, 0, 0), died=(False,) * 4)
    write(replays / 'four.dem', at=clock.t - 3)
    w.tick(); w.tick()
    rows = {r['name']: r for r in w.status()['recent']}
    assert rows['four.dem']['state'] == 'skipped' and 'No rounds' in rows['four.dem']['message']
    with pytest.raises(ValueError):
        w.configure({'steamid': 'not-a-steam-id'})


def test_missing_account_and_switching_off(tmp_path):
    w, replays, queue, calls, state, clock = make(tmp_path, accounts=[])
    w.configure({'enabled': True})
    clock.t += 60
    write(replays / 'a.dem', at=clock.t - 10)
    w.tick(); w.tick()
    assert calls == [] and w.status()['recent'][0]['state'] == 'skipped'
    w.configure({'enabled': False})
    write(replays / 'b.dem', at=clock.t - 9)
    w.tick(); w.tick()
    assert w.status()['enabled'] is False and len(w.status()['recent']) == 1


def test_server_reports_and_configures_auto_recording(tmp_path, monkeypatch):
    monkeypatch.setenv('POVFORGE_STATE', str(tmp_path / 'state'))
    from povforge.gui import server
    app = server.App()
    replays = tmp_path / 'replays'; replays.mkdir()
    app.auto.folder_finder = lambda: replays
    app.auto._looked = False
    app.auto.accounts_finder = lambda: [{'steamid': ME, 'name': 'Chester', 'recent': True}]
    app.auto._accounts = None
    app.auto.configure({'enabled': True, 'mode': 'kill_events'})
    status = app.auto.status()
    assert status['enabled'] and status['mode'] == 'kill_events' and status['folder'] == str(replays)
    assert status['steamid'] == ME
    assert json.loads((tmp_path / 'state' / 'povforge' / 'app.json').read_text(encoding='utf-8'))['auto_mm'] is True
    app.job.state = 'running'
    assert app._game_busy() == '', 'a running recording owns the game'
    app.job.state = 'idle'


@pytest.mark.skipif(cdp.find_browser() is None, reason='Edge/Chrome required')
def test_auto_mode_is_a_sidebar_peer_that_explains_the_flow(workspace_site):
    url, state = workspace_site
    with cdp.Browser(size=(1920, 1080)) as browser:
        page = browser.page()
        try:
            page.call('Page.enable')
            page.call('Page.addScriptToEvaluateOnNewDocument', source="window.uiErrors=[];window.addEventListener('error',e=>uiErrors.push(e.message))")
            page.call('Page.navigate', url=url)
            assert page.wait_for("document.querySelectorAll('.demo-card').length===5", 15)
            page.evaluate("window.app=Alpine.$data(document.body)")
            assert page.evaluate("document.querySelectorAll('.modes button')[5].textContent.trim()") == '官匹自动录制'
            assert page.evaluate("document.querySelector('.settings-tabs [data-settings-tab=auto]')") is None
            page.evaluate("document.querySelectorAll('.modes button')[5].click()")
            assert page.wait_for("document.querySelector('.auto-page')?.checkVisibility() && !document.querySelector('.library').checkVisibility()", 3)
            assert page.evaluate("document.querySelectorAll('.modes button')[5].getAttribute('aria-selected')") == 'true'
            assert page.evaluate("document.querySelectorAll('.modes button')[0].getAttribute('aria-selected')") == 'false'
            text = page.evaluate("document.querySelector('.auto-page').textContent")
            for phrase in ('你的比赛', '退出 CS2', '你不需要自己打开 CS2', '注意事项'):
                assert phrase in text, phrase
            assert page.evaluate("document.querySelectorAll('.auto-steps li').length") == 4
            page.evaluate("const s=document.querySelector('#auto-mm');s.checked=true;s.dispatchEvent(new Event('change',{bubbles:true}))")
            assert page.wait_for("app.auto.enabled===true", 3)
            page.evaluate("const m=document.querySelector('#auto-mode');m.value='kill_events';m.dispatchEvent(new Event('change',{bubbles:true}))")
            assert page.wait_for("app.auto.mode==='kill_events'", 3)
            assert [p for p in state['auto_posts'] if not p.get('refresh')] == [{'enabled': True}, {'mode': 'kill_events'}]
            assert page.wait_for("document.querySelector('.auto-tab.on')", 3), 'the sidebar entry shows it is on'
            state['auto'].update(waiting='cs2', recent=[{'name': 'match730_x.dem', 'title': 'Chester 官匹击杀视角 · Mirage', 'state': 'queued', 'message': '已加入录制队列：3 个回合。', 'at': 1}])
            page.evaluate("app.refresh()", await_promise=True)
            assert page.wait_for("document.querySelector('#auto-mm').closest('.row').textContent.includes('退出 CS2 后自动开始')", 3)
            assert page.wait_for("document.querySelector('.auto-recent')?.textContent.includes('已加入录制队列：3 个回合')", 3)
            page.evaluate("document.querySelector('.auto-notes-link').click()")
            assert page.wait_for("document.querySelector('.notes-page')?.checkVisibility()", 3)
            page.evaluate("document.querySelectorAll('.modes button')[1].click()")
            assert page.wait_for("!document.querySelector('.notes-page').checkVisibility() && app.reelOpen", 3)
            page.evaluate("app.lang='en';app.openAuto()")
            assert page.wait_for("document.querySelector('.auto-page').textContent.includes('Your Matches')", 3)
            assert page.evaluate('uiErrors') == []
        finally:
            page.close()


@pytest.mark.skipif(cdp.find_browser() is None, reason='Edge/Chrome required')
def test_first_use_opens_the_notes_at_the_top_of_the_sidebar(workspace_site):
    url, state = workspace_site
    state['prefs']['notes_seen'] = False
    with cdp.Browser(size=(1920, 1080)) as browser:
        page = browser.page()
        try:
            page.call('Page.enable')
            page.call('Page.addScriptToEvaluateOnNewDocument', source="window.uiErrors=[];window.addEventListener('error',e=>uiErrors.push(e.message))")
            page.call('Page.navigate', url=url)
            # Before the stylesheet/Alpine load, x-cloak sections can look visible; wait for boot.
            assert page.wait_for("!!window.Alpine && !!document.body._x_dataStack && Alpine.$data(document.body).booted"
                                 " && document.querySelector('.notes-page')?.checkVisibility()", 15)
            page.evaluate("window.app=Alpine.$data(document.body)")
            assert page.evaluate("document.querySelector('.sidebar').firstElementChild.classList.contains('notes-nav')"), 'notes are the first sidebar entry'
            first = page.evaluate("document.querySelector('.notes-nav').getBoundingClientRect().top")
            modes = page.evaluate("document.querySelector('.modes').getBoundingClientRect().top")
            assert first < modes
            assert page.evaluate("document.querySelector('.notes-nav').textContent").count('第一次使用请先看') == 1
            assert page.evaluate("document.querySelector('.notes-dot').checkVisibility()")
            text = page.evaluate("document.querySelector('.notes-page').textContent")
            for phrase in ('录制前', '录制时', '官匹自动录制', '下载完一定要退出 CS2', '不需要、也不要自己打开 CS2', '反作弊'):
                assert phrase in text, phrase
            assert not page.evaluate("document.querySelector('.library').checkVisibility()")
            page.evaluate("document.querySelector('.notes-ack').click()")
            assert page.wait_for("app.prefs.notes_seen===true && document.querySelector('.library').checkVisibility()", 3)
            assert state['prefs']['notes_seen'] is True
            assert page.wait_for("!document.querySelector('.notes-dot').checkVisibility()", 3)
            assert page.evaluate("document.querySelector('.notes-nav').textContent").count('录制前须知') == 1
            page.call('Page.navigate', url=url)
            assert page.wait_for("document.querySelectorAll('.demo-card').length===5 && document.querySelector('.library').checkVisibility()", 15)
            assert not page.evaluate("document.querySelector('.notes-page').checkVisibility()"), 'shown only until read'
            assert page.evaluate('uiErrors') == []
        finally:
            page.close()

def test_main_runs_with_an_app_that_has_no_watcher(monkeypatch):
    """Isolated hosts (like the native-window probe) replace App without a watcher."""
    from povforge.gui import server
    from types import SimpleNamespace
    started = []

    class App:
        references = SimpleNamespace(close=lambda: started.append('refs'))
        checker = SimpleNamespace(close=lambda: started.append('checker'))
        window = None
        def quit_reason(self, now): return ''

    class FakeServer:
        server_address = ('127.0.0.1', 1)
        def __init__(self, *a): pass
        def serve_forever(self): started.append('served')
        def shutdown(self): pass
        def server_close(self): started.append('closed')
    monkeypatch.setattr(server, 'App', App)
    monkeypatch.setattr(server, 'ThreadingHTTPServer', FakeServer)
    monkeypatch.setattr(server, 'make_handler', lambda app: None)
    server.main(0, open_browser=False)
    assert started == ['served', 'closed', 'refs', 'checker']
