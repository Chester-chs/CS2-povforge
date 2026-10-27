"""Recording with each player's own look: prosettings.net data, demo crosshair, 4:3 windows."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from povforge import cdp, hlae, pro_settings
from povforge.config import load_config
from test_workspace_browser import workspace_site  # noqa: F401

FIXTURE = Path(__file__).with_name('fixture_prosettings_fallen.html')
CODE = 'CSGO-ssxCh-Y9LFi-B9amu-NWkZo-ObaAB'


def fallen():
    return pro_settings.look(pro_settings.parse(FIXTURE.read_text(encoding='utf-8')), 'https://prosettings.net/players/fallen/')


def test_prosettings_page_becomes_a_recording_look():
    look = fallen()
    assert look['name'] == 'FalleN' and look['resolution'] == '1280x960' and look['aspect'] == '4:3'
    assert look['fit'] == 'stretch' and look['game'] == [1440, 1080], '4:3 recorded at 1080 lines, then stretched'
    for c in ('viewmodel_fov 60', 'viewmodel_offset_x 1', 'viewmodel_offset_y 1', 'viewmodel_offset_z -1',
              'cl_crosshairstyle 4', 'cl_crosshaircolor_r 213', 'cl_crosshair_drawoutline 0', 'hud_scaling 1', 'cl_bobcycle 0.98'):
        assert c in look['commands'], c
    assert 'crosshair_code' not in look, "a visitor's comment is not the player's crosshair"
    assert look['not_applied']['brightness'] == '93%' and 'shader_detail' in look['not_applied']
    assert all(hlae.LOOK_COMMAND.fullmatch(c) for c in look['commands'])
    assert not any(c.startswith(('sensitivity', 'zoom_', 'dpi')) for c in look['commands']), 'mouse settings change nothing visible'


def test_names_and_links():
    assert pro_settings.slug('m0NESY') == 'm0nesy' and pro_settings.page_url('ZywOo') == 'https://prosettings.net/players/zywoo/'
    assert pro_settings.valid_url('https://prosettings.net/players/fallen/')
    for bad in ('http://prosettings.net/players/fallen/', 'https://evil.example/players/x/', 'https://prosettings.net/players/../x'):
        assert not pro_settings.valid_url(bad)
    wide = pro_settings.look({'fields': {'resolution': '1920x1080', 'aspect_ratio': '16:9', 'scaling_mode': 'Native'}})
    assert wide['fit'] == 'native' and wide['game'] is None
    bars = pro_settings.look({'fields': {'resolution': '1024x768', 'scaling_mode': 'Black Bars'}})
    assert bars['fit'] == 'pad' and bars['game'] == [1440, 1080]
    odd = pro_settings.look({'fields': {'viewmodel_fov': '60; quit', 'cl_hud_color': 'Team Color'}})
    assert odd['commands'] == ['cl_hud_color 11']


def test_recording_settings_for_one_player():
    s = hlae.RecordSettings(player_look=True, looks={'765': {'game_width': 1440, 'game_height': 1080, 'fit': 'stretch',
                                                             'commands': ['viewmodel_fov 60', 'viewmodel_fov 60; quit', 'exec x']}})
    one = hlae.for_player(s, '765', CODE)
    assert hlae.game_size(one) == (1440, 1080) and (one.width, one.height) == (1920, 1080)
    assert one.look_commands == ['viewmodel_fov 60', 'cl_show_observer_crosshair 2', f'apply_crosshair_code {CODE}']
    cmds = hlae.setup_commands(one)
    assert cmds[-3:] == one.look_commands
    launch = hlae.launch_command(Path('HLAE.exe'), Path('cs2.exe'), one)
    assert '-width 1440 -height 1080' in launch[-1]
    other = hlae.for_player(s, '999', '')
    assert hlae.game_size(other) == (1920, 1080) and other.look_commands == ['cl_show_observer_crosshair 2']
    plain = hlae.RecordSettings()
    assert hlae.for_player(plain, '765', CODE) is plain
    assert hlae.quality_key(plain) == {'width': 1920, 'height': 1080, 'fps': 60}, 'existing takes stay reusable'
    assert hlae.quality_key(one) != hlae.quality_key(other), 'a different look is a different take'
    assert hlae.fit_filter((1440, 1080), (1920, 1080), 'stretch') == 'scale=1920:1080:flags=lanczos,setsar=1'
    assert 'pad=1920:1080' in hlae.fit_filter((1440, 1080), (1920, 1080), 'pad')
    assert hlae.fit_filter((1920, 1080), (1920, 1080), 'stretch') is None


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'), reason='FFmpeg required')
def test_a_4_3_take_is_stretched_to_the_video_size(tmp_path):
    take = tmp_path / 'take'; take.mkdir()
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc=size=144x108:rate=10',
                    '-t', '1', '-pix_fmt', 'yuv420p', str(take / 'video.mp4')], check=True)
    s = hlae.RecordSettings(width=192, height=108, game_width=144, game_height=108)
    out = tmp_path / 'clip.mp4'
    hlae.mux_take(take, out, 'ffmpeg', s)
    probe = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                                       'stream=width,height,sample_aspect_ratio', '-of', 'json', str(out)],
                                      capture_output=True, text=True, check=True).stdout)['streams'][0]
    assert (probe['width'], probe['height']) == (192, 108)
    assert probe.get('sample_aspect_ratio', '1:1') == '1:1', 'stretched, not displayed as 4:3'


def test_job_config_carries_looks_to_the_recorder(tmp_path, monkeypatch):
    monkeypatch.setenv('POVFORGE_STATE', str(tmp_path / 'state'))
    from povforge.gui import server
    prefs = server.load_prefs()
    prefs['output'] = str(tmp_path / 'out')
    path = server.write_job_config(prefs, None, {'765': fallen(), 'bad id': fallen()})
    cfg = load_config(path)
    assert cfg.record.player_look is True
    assert list(cfg.record.looks) == ['765']
    look = cfg.record.looks['765']
    assert (look['game_width'], look['game_height'], look['fit']) == (1440, 1080, 'stretch')
    assert 'viewmodel_fov 60' in look['commands']
    prefs['player_look'] = False
    assert load_config(server.write_job_config(prefs, None, {})).record.player_look is False


def test_lookups_are_cached_overridable_and_survive_being_offline(tmp_path, monkeypatch):
    monkeypatch.setenv('POVFORGE_STATE', str(tmp_path / 'state'))
    from povforge.gui import server
    prefs = {'player_look': True, 'player_look_urls': {}}
    calls = []

    def found(url):
        calls.append(url)
        return fallen()
    a = server.player_look(prefs, '765', 'FalleN', lookup=found)
    assert a['state'] == 'found' and a['url'] == 'https://prosettings.net/players/fallen/'
    server.player_look(prefs, '765', 'FalleN', lookup=found)
    assert len(calls) == 1, 'cached for a week'

    def offline(url):
        raise OSError('no network')
    b = server.player_look(prefs, '765', 'FalleN', refresh=True, lookup=offline)
    assert b['state'] == 'found' and b['stale'], 'the last good copy is kept offline'
    prefs['player_look_urls']['765'] = 'off'
    assert server.player_look(prefs, '765', 'FalleN', lookup=found)['state'] == 'off'
    prefs['player_look_urls'] = {}
    err = type('E', (Exception,), {'code': 404})
    def missing(url):
        raise err('not found')
    c = server.player_look(prefs, '42', 'Nobody Here', lookup=missing)
    assert c['state'] == 'missing'
    item = {'kind': 'reel', 'reel': [{'steamid': '765', 'name': 'FalleN → Nobody Here', 'opponent': '42'},
                                      {'steamid': '765', 'name': 'FalleN → Nobody Here', 'opponent': '42'}]}
    assert server.task_players(item) == [('765', 'FalleN'), ('42', 'Nobody Here')]
    looks = server.task_looks(prefs, item, lookup=found)
    assert list(looks) == ['765'], 'only found looks are applied; others use the user settings'
    assert server.task_looks({'player_look': False}, item, lookup=found) == {}


def test_demo_crosshair_is_the_most_used_code(monkeypatch):
    import pandas as pd
    from povforge import demo

    class Parser:
        def parse_ticks(self, wanted, players=None):
            return pd.DataFrame({'tick': [1, 2, 3, 4], 'steamid': [765, 765, 765, 1],
                                 'crosshair_code': [CODE, CODE, 'CSGO-AAAAA-BBBBB-CCCCC-DDDDD-EEEEE', 'CSGO-ZZZZZ-ZZZZZ-ZZZZZ-ZZZZZ-ZZZZZ']})
    monkeypatch.setattr(demo, '_parser', lambda path: Parser())
    assert demo.player_crosshair('x.dem', '765') == CODE
    monkeypatch.setattr(demo, '_parser', lambda path: type('P', (), {'parse_ticks': lambda self, w, players=None: pd.DataFrame({'tick': [1]})})())
    assert demo.player_crosshair('x.dem', '765') == ''


@pytest.mark.skipif(cdp.find_browser() is None, reason='Edge/Chrome required')
def test_recording_panel_shows_each_recorded_players_look(workspace_site):
    url, state = workspace_site
    state['looks'] = {'a': {**fallen(), 'state': 'found', 'url': 'https://prosettings.net/players/fallen/'}}
    with cdp.Browser(size=(1920, 1080)) as browser:
        page = browser.page()
        try:
            page.call('Page.enable')
            page.call('Page.addScriptToEvaluateOnNewDocument', source="window.uiErrors=[];window.addEventListener('error',e=>uiErrors.push(e.message))")
            page.call('Page.navigate', url=url)
            assert page.wait_for("document.querySelectorAll('.demo-card').length===5", 15)
            page.evaluate("window.app=Alpine.$data(document.body)")
            assert page.evaluate("document.querySelectorAll('.look-row').length") == 0
            page.evaluate("app.pickDemo('C:/Demos/match-0.dem')", await_promise=True)
            page.evaluate("app.player=app.demo.teams[0].players[0]")
            assert page.wait_for("document.querySelector('.look-row')?.textContent.includes('1280×960 4:3 拉伸')", 4)
            text = page.evaluate("document.querySelector('.look-row').textContent")
            assert '持枪 FOV 60（1, 1, -1）' in text and '准星' in text
            page.evaluate("app.demo.teams[1].players=[{steamid:'b',name:'Other'}];app.demo.duels=[{round:1,tick:5,attacker:'a',victim:'b'}];app.openReel(true,'duel');app.reel.sources[0].opponent='b';app.recompute()")
            assert page.wait_for("document.querySelectorAll('.look-row').length===2", 4), 'a duel records both players'
            assert page.wait_for("document.querySelectorAll('.look-row')[1].textContent.includes('没找到')", 4)
            page.evaluate("[...document.querySelectorAll('.look-row')[0].querySelectorAll('button')].find(b=>b.textContent.includes('用我的设置')).click()")
            assert page.wait_for("document.querySelectorAll('.look-row')[0].textContent.includes('已改为使用你自己的设置')", 4)
            page.evaluate("const s=document.querySelector('#player-look');s.checked=false;s.dispatchEvent(new Event('change',{bubbles:true}))")
            assert page.wait_for("document.querySelectorAll('.look-row').length===0 && app.prefs.player_look===false", 4)
            assert state['prefs']['player_look'] is False
            assert page.evaluate('uiErrors') == []
        finally:
            page.close()
