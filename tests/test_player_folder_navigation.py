"""Player destinations and the finished-library folder tree, without recording."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from povforge import cdp
from test_workspace_browser import workspace_site


@pytest.mark.skipif(not shutil.which('node'), reason='Node required')
def test_folder_tree_groups_real_paths_and_filters_without_prefix_collisions():
    script = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert'); let factory;
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),{
 document:{addEventListener:(_,fn)=>fn()},Alpine:{data:(_,fn)=>factory=fn},setTimeout,clearTimeout
});
const app=factory(); app.lang='en';
app.reel.sources=[{path:'x.dem',info:{recording_details:{rounds:[{number:1,end:50}],seconds:{},
 events:[{round:1,time:10,attacker:'a',victim:'b',pov:true},{round:1,time:17.5,attacker:'a',victim:'c',pov:true},
 {round:1,time:30,attacker:'a',victim:'d',pov:true}]}}}];
app.reel.items=[{path:'x.dem',round:1,steamid:'a'}];
for(const mode of ['kill_events','kills_deaths']) {
 app.reel.content=mode; assert.strictEqual(app.reelEstimate.seconds,23.5); assert.strictEqual(app.reelEstimate.segments,2);
}
app.reel.content='kills'; assert.strictEqual(app.reelEstimate.seconds,28);
app.prefs={output:'C:/Videos',by_player:false,player_folders:{
 a:{name:'donk666',folder:'donk666'},b:{name:'m0NESY',folder:'m0NESY',path:'D:/Custom/m0NESY'},
 c:{name:'New player',folder:'New player'}}};
app.libraryVideos=[
 {path:'C:\\Videos\\donk666\\A.mp4',name:'AK clip',mode:'kill_events'},
 {path:'c:/videos/DONK666/B.mp4',name:'AWP clip',mode:'match'},
 {path:'C:/Videos/donk666-other/C.mp4',name:'Other clip',mode:'match'},
 {path:'D:/Custom/m0NESY/D.mp4',name:'AWP clip',mode:'kill_events'},
 {path:'C:/Videos/old-player/E.mp4',name:'Older video',mode:'unknown'},
 {path:'C:/Videos/root.mp4',name:'Shared video',mode:'unknown'}];
const folders=app.videoFolders;
const donk=folders.find(f=>f.name==='donk666');
assert.ok(donk,'known player folder is listed even with by-player disabled');
assert.strictEqual(donk.count,2,'mixed slashes/case refer to one Windows folder');
assert.strictEqual(folders.find(f=>f.name==='New player').count,0,'empty known folders remain selectable');
assert.ok(folders.some(f=>f.name==='old-player'),'existing videos without player metadata are grouped');
app.videoFolder=donk.path;
assert.strictEqual(app.filteredVideos.length,2,'only direct contents, not a similarly named folder');
app.videoMode='kill_events'; assert.strictEqual(app.filteredVideos.length,1);
app.videoQuery='AWP'; assert.strictEqual(app.filteredVideos.length,0);
app.videoFolder=folders.find(f=>f.name==='m0NESY').path;
assert.strictEqual(app.filteredVideos.length,1,'folder, mode and search combine');
app.videoFolder=''; app.videoMode='all'; app.videoQuery='';
assert.strictEqual(app.filteredVideos.length,6,'all videos still accessible');
let chips=app.videoModeChips;
assert.strictEqual(JSON.stringify(chips.map(c=>[c.mode,c.count])),JSON.stringify([['all',6],['match',2],['kill_events',2],['unknown',2]]),'chips count the current view in sidebar order');
app.videoFolder=donk.path; chips=app.videoModeChips;
assert.strictEqual(JSON.stringify(chips.map(c=>[c.mode,c.count])),JSON.stringify([['all',2],['match',1],['kill_events',1]]),'chips follow the selected folder');
app.videoMode='duel'; assert.ok(app.videoModeChips.some(c=>c.mode==='duel'&&c.count===0),'the selected chip stays visible');
app.libraryVideos.push({path:'C:/Videos/donk666/F.mp4',name:'Legacy',mode:'old-mode'}); app.videoMode='unknown';
assert.strictEqual(app.filteredVideos.length,1,'unlisted modes count as existing videos');
'''
    result = subprocess.run(['node', '-', str(Path(__file__).parents[1] / 'povforge/gui/static/app.js')],
                            input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(cdp.find_browser() is None, reason='Edge/Chrome required')
def test_destinations_follow_active_players_and_sidebar_folders_show_contents(workspace_site):
    url, state = workspace_site
    state['prefs']['player_folders'] = {
        'a': {'name': 'Example player', 'folder': 'Example player'},
        'b': {'name': 'm0NESY', 'folder': 'm0NESY', 'path': 'D:/Custom/m0NESY'},
    }
    state['library'] = {'items': [
        {'path':'C:/Videos/Example player/A.mp4','name':'AK round','mode':'kill_events','players':['Example player'],'maps':['Dust2'],'size':1024,'mtime':1792600000},
        {'path':'D:/Custom/m0NESY/B.mp4','name':'AWP round','mode':'match','players':['m0NESY'],'maps':['Nuke'],'size':2048,'mtime':1792600000},
    ]}
    with cdp.Browser(size=(1920,1080)) as browser:
        page = browser.page()
        try:
            page.call('Page.enable')
            page.call('Page.addScriptToEvaluateOnNewDocument', source="window.uiErrors=[];window.addEventListener('error',e=>uiErrors.push(e.message))")
            page.call('Page.navigate', url=url)
            assert page.wait_for("document.querySelectorAll('.demo-card').length===5",15)
            page.evaluate("window.app=Alpine.$data(document.body)")
            assert page.evaluate("document.querySelectorAll('.recording-panel .folder-row').length") == 0
            assert page.evaluate("document.querySelector('label[for=by-player] b').textContent.trim()") == '按选手 ID 建文件夹'
            page.evaluate("app.pickDemo('C:/Demos/match-0.dem')",await_promise=True)
            page.evaluate("app.player=app.demo.teams[0].players[0]")
            assert page.wait_for("document.querySelectorAll('.recording-panel .folder-row').length===1",3)
            assert 'm0NESY' not in page.evaluate("document.querySelector('.recording-panel').textContent")
            page.evaluate("app.demo.teams[1].players=[{steamid:'b',name:'m0NESY'}];app.openReel(true,'kill_events')")
            assert page.wait_for("document.querySelectorAll('.recording-panel .folder-row').length===1",3)
            page.evaluate("app.reel.steamid='b';app.recompute()")
            assert page.wait_for("document.querySelector('.recording-panel .folder-row .path')?.textContent==='D:/Custom/m0NESY'",3)
            page.evaluate("app.setReelContent('duel');app.reel.sources[0].opponent='a'")
            # A duel is filed under player A only, matching the backend.
            assert page.wait_for("document.querySelectorAll('.recording-panel .folder-row').length===1",3)
            assert page.evaluate("document.querySelector('.recording-panel .folder-row .path').textContent") == 'D:/Custom/m0NESY'
            assert page.evaluate("!document.querySelector('.recording-panel .multi-folder').checkVisibility()")
            page.evaluate("app.setReelContent('kills');app.reel.sources.push({path:'C:/Demos/match-1.dem',info:app.reel.sources[0].info,steamid:'a',opponent:''});app.setMode('each');app.reel.sources[0].steamid='b';app.reel.sources[1].steamid='a';app.recompute()")
            assert page.wait_for("document.querySelector('.recording-panel .multi-folder')?.checkVisibility() && document.querySelectorAll('.recording-panel .folder-row').length===0",3)
            assert page.evaluate("document.querySelector('.recording-panel .multi-folder .path').textContent").endswith('多人集锦')
            page.evaluate("app.openSettings('saving')",await_promise=True)
            assert page.wait_for("document.querySelector('.saving-page #by-player')?.checkVisibility()",3)
            assert page.wait_for("document.querySelectorAll('.settings-player-folder').length===2",3)
            page.evaluate("app.settingsOpen=false")
            page.evaluate("app.openLibrary()")
            assert page.wait_for("document.querySelectorAll('.recording-panel .folder-row').length===0",3)
            page.evaluate("document.querySelector('.videos-nav').click()")
            assert page.wait_for("document.querySelector('.videos-toggle')?.getAttribute('aria-expanded')==='true'",3)
            assert page.wait_for("document.querySelectorAll('.video-folder').length===2",3)
            page.evaluate("Array.from(document.querySelectorAll('.video-folder')).find(b=>b.textContent.includes('m0NESY')).click()")
            assert page.wait_for("document.querySelectorAll('.video-row').length===1 && document.querySelector('.video-row').textContent.includes('AWP round')",3)
            assert page.evaluate("document.querySelector('.video-folder-location').textContent") == 'D:/Custom/m0NESY'
            page.evaluate("document.querySelector('.videos-toggle').click()")
            assert page.wait_for("document.querySelector('#video-folders').getBoundingClientRect().height===0",3)
            page.evaluate("document.querySelector('.videos-toggle').click();document.querySelector('.videos-nav').click()")
            assert page.wait_for("document.querySelectorAll('.video-row').length===2",3)
            for theme, rgb in [('dark','rgb(255, 255, 255)'),('light','rgb(0, 0, 0)')]:
                page.evaluate(f"app.prefs.appearance='{theme}';app.applyTheme()")
                assert page.wait_for(f"getComputedStyle(document.querySelector('.video-folder span')).color==={json.dumps(rgb)}",3)
            assert page.evaluate('uiErrors') == []
        finally:
            page.close()
