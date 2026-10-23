"""Workspace navigation must not repeat onboarding or lose reel selections."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which('node'), reason='Node required')
def test_workspace_startup_navigation_and_latest_inspection():
    script = r'''
const fs=require('fs'), vm=require('vm'), assert=require('assert');
let factory;
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'), {
 document:{addEventListener:(_,fn)=>fn(),getElementById:()=>({}),documentElement:{},querySelector:()=>({scrollTo:()=>{}})},
 Alpine:{data:(_,fn)=>factory=()=>Object.assign(fn(),{$nextTick:callback=>callback()})}, navigator:{language:'en'}, window:{addEventListener:()=>{}},
 fetch:async()=>({text:async()=>''}), setTimeout:()=>1, clearTimeout:()=>{}
});
async function boot(configured, extra={}) {
 const a=factory(); a.refresh=async()=>{}; a.applyTheme=()=>{}; a.loadDemos=()=>{}; a.$watch=()=>{};
 a.prefs={folders_set:configured}; a.setup={cs2:true,hlae:true,ffmpeg:true,...extra};
 await a.boot(); return a;
}
async function test() {
 const first=await boot(false); assert.strictEqual(first.setupOpen,true);
 const a=await boot(true); assert.strictEqual(a.setupOpen,false); assert.strictEqual(a.libraryOpen,true);
 const broken=await boot(true,{hlae:false}); assert.strictEqual(broken.setupOpen,true);
 const recovery=await boot(true,{settings_pending:true}); assert.strictEqual(recovery.setupOpen,true);
 a.openSetup(); a.openMatchMode(); assert.strictEqual(a.setupOpen,false); assert.strictEqual(a.libraryOpen,true);
 a.openReel(false); assert.strictEqual(a.reelOpen,true); assert.strictEqual(a.libraryOpen,true);
 a.reel.sources=[{path:'a.dem',info:{teams:[]}}]; a.editReel(); assert.strictEqual(a.libraryOpen,false);
 a.openLibrary(); assert.strictEqual(a.reel.sources.length,1); assert.strictEqual(a.reelOpen,true);
 a.demos=[{path:'a.dem',name:'FACEIT-a.dem',map:'Dust2'},{path:'b.dem',name:'b.dem',map:'Nuke'}];
 a.libraryQuery='dust'; assert.strictEqual(a.libraryDemos.length,1); assert.strictEqual(a.libraryDemos[0].path,'a.dem');
 a.libraryQuery='unknown'; assert.strictEqual(a.libraryDemos.length,0);
 let resolveA, resolveB;
 a.post=(_,b)=>new Promise(r=>{if(b.path==='a.dem') resolveA=r; else resolveB=r});
 const old=a.pickDemo('a.dem'), latest=a.pickDemo('b.dem');
 resolveB({path:'b.dem',rounds:2}); await latest;
 resolveA({path:'a.dem',rounds:5}); await old;
 assert.strictEqual(a.demo.path,'b.dem','late replies cannot replace the current selection');
 assert.strictEqual(a.chosenRounds.length,2);
 a.openLibrary(); assert.strictEqual(a.libraryOpen,true);
 const leaving=a.pickDemo('a.dem'); a.openLibrary(); resolveA({path:'a.dem',rounds:5}); await leaving;
 assert.strictEqual(a.demo,null); assert.strictEqual(a.inspecting,false); assert.strictEqual(a.libraryOpen,true);
 const api=factory(); api.get=async()=>({error:'Folder unavailable'}); await api.loadDemos();
 assert.strictEqual(api.libraryError,'Folder unavailable'); assert.strictEqual(api.demos.length,0);
 const modes=factory(); modes.lang='zh';
 assert.strictEqual(modes.currentModeTitle,'Demo整场录制');
 for (const [content,title] of [['kills','高光集锦'],['kill_events','Demo击杀视角'],['kills_deaths','Demo击杀和死亡视角'],['duel','双人对位数据']]) {
   modes.openReel(false,content);
   assert.strictEqual(modes.currentModeTitle,title);
   assert.strictEqual(modes.reel.content,content);
   assert.strictEqual(modes.libraryOpen,true);
 }
 modes.reel.sources=[{path:'saved.dem',info:{teams:[]}}];
 modes.reel.title='Custom video'; modes.reel.titleEdited=true;
 modes.openReel(false,'kill_events');
 assert.strictEqual(modes.reel.sources[0].path,'saved.dem');
 assert.strictEqual(modes.reel.title,'Custom video');
 modes.openReel(false); assert.strictEqual(modes.reel.content,'kills','highlight navigation must leave the event mode');
 modes.reel.items=[{key:'manual-choice',round:2}];
 modes.openMatchMode(); modes.openReel(false);
 assert.strictEqual(modes.reel.items[0].key,'manual-choice','reopening the same mode must preserve hand-picked moments');
 modes.openMatchMode(); assert.strictEqual(modes.currentModeTitle,'Demo整场录制');
 modes.settingsOpen=true; modes.job={state:'running', item:7};
 modes.openItem({id:7});
 assert.strictEqual(modes.settingsOpen,false,'queue navigation must leave Settings so stop controls remain reachable');
 assert.strictEqual(modes.showRun,true);
 const appearance=factory(); appearance.applyTheme=()=>{};
 appearance.prefs={popup_radius:14};
 appearance.get=async()=>({prefs:{popup_radius:14},setup:{},job:{}});
 let savedRadius;
 appearance.post=async(_,body)=>{savedRadius=body.popup_radius;return {...body}};
 appearance.previewPopupRadius(22);
 await appearance.refresh();
 assert.strictEqual(appearance.prefs.popup_radius,22,'polling must preserve an active radius edit');
 await appearance.savePopupRadius(22);
 assert.strictEqual(savedRadius,22);
}
test().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node', '-', str(Path(__file__).parents[1] / 'povforge/gui/static/app.js')],
                            input=script, text=True, encoding='utf-8', capture_output=True)
    assert result.returncode == 0, result.stderr
