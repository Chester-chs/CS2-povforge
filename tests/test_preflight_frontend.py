import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which('node'), reason='Node required')
def test_estimates_weapons_and_library_filter_follow_actual_selections():
    script = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');let factory;
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),{
 document:{addEventListener:(_,fn)=>fn()},Alpine:{data:(_,fn)=>factory=fn},
 navigator:{language:'en'},window:{},setTimeout:()=>1,clearTimeout:()=>{}});
const app=factory();app.lang='en';app.prefs={record_fps:60,intro:false};
const player={steamid:'a',name:'A',rounds_k:[2],rounds_died:[true]};
const info={rounds:1,teams:[{players:[player,{steamid:'b',name:'B'}]}],
 duels:[{round:1,tick:160,attacker:'b',victim:'a'}],recording_details:{version:1,
 rounds:[{number:1,start:0,end:20}],seconds:{a:[18]},events:[
 {round:1,tick:80,time:8,attacker:'a',victim:'c',weapon:'ak47',headshot:true,pov:true},
 {round:1,tick:100,time:10,attacker:'a',victim:'b',weapon:'m4a1',pov:true},
 {round:1,tick:160,time:16,attacker:'b',victim:'a',weapon:'awp',pov:true}]}};
app.demo=info;app.player=player;app.customRounds=false;
assert.strictEqual(app.matchEstimate.seconds,18);
assert.strictEqual(app.matchEstimate.segments,1);
app.customRounds=true;app.chosenRounds=[];assert.strictEqual(app.matchEstimate.seconds,0);
app.reel.sources=[{path:'x.dem',info,steamid:'a',opponent:'b'}];
app.reel.items=[{path:'x.dem',steamid:'a',opponent:'b',round:1}];
app.reel.content='kill_events';
assert.strictEqual(app.reelEstimate.seconds,7.5,'overlapping kill windows merge');
assert.strictEqual(app.reelEstimate.segments,1);
assert.match(app.weaponSummary(app.reel.items[0]),/AK-47/);
assert.match(app.weaponSummary(app.reel.items[0]),/M4A4/);
assert.doesNotMatch(app.weaponSummary(app.reel.items[0]),/AWP/);
app.reel.content='kills_deaths';assert.strictEqual(app.reelEstimate.seconds,13);
assert.match(app.weaponSummary(app.reel.items[0]),/AWP/);
app.reel.content='duel';assert.strictEqual(app.reelEstimate.seconds,11);
assert.strictEqual(app.itemEvents(app.reel.items[0]).length,1);
app.reel.content='kills';assert.strictEqual(app.reelEstimate.seconds,7.5);
app.libraryVideos=[{name:'A highlight',players:['A'],maps:['Dust2'],mode:'kills',missing:false}];
app.videoQuery='dust';app.videoMode='all';assert.strictEqual(app.filteredVideos.length,1);
app.videoMode='duel';assert.strictEqual(app.filteredVideos.length,0);
'''
    result = subprocess.run(['node', '-', str(Path(__file__).parents[1] / 'povforge/gui/static/app.js')],
                            input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
