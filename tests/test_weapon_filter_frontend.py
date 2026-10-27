import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which('node'),reason='Node required')
def test_mixed_weapon_preview_estimate_and_request_keep_same_windows():
    script=r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');let factory;
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),{
 document:{addEventListener:(_,fn)=>fn()},Alpine:{data:(_,fn)=>factory=fn},setTimeout,clearTimeout});
async function main(){
 const app=factory();app.lang='en';app.toast=()=>{};app.scrollContentTop=()=>{};
 const player={steamid:'a',name:'A',rounds_k:[3],rounds_event_k:[3]};
 const info={map_pretty:'Dust2',teams:[{players:[player]}],recording_details:{rounds:[{number:1,end:50}],
  seconds:{a:[50]},events:[{round:1,time:10,tick:100,attacker:'a',victim:'b',weapon:'ak47',pov:true},
  {round:1,time:15,tick:150,attacker:'a',victim:'c',weapon:'awp',pov:true},
  {round:1,time:35,tick:350,attacker:'a',victim:'d',weapon:'ak47',pov:true}]}};
 app.reel.sources=[{path:'x.dem',info,steamid:'a'}];app.reel.steamid='a';app.reel.content='kill_events';
 info.duels=info.recording_details.events.map(e=>({...e}));
 app.reel.weapons=['awp'];app.recompute();
 assert.strictEqual(app.reel.items.length,1);
 assert.strictEqual(app.reel.items[0].k,2,'round label counts the retained mixed sequence');
 assert.strictEqual(app.reelEstimate.seconds,13);assert.strictEqual(app.reelEstimate.segments,1);
 assert.match(app.weaponSummary(app.reel.items[0]),/AK-47 ×1/);assert.match(app.weaponSummary(app.reel.items[0]),/AWP ×1/);
 assert.strictEqual(app.itemEvents(app.reel.items[0]).length,2);
 assert.strictEqual(app.victimEntries.length,2,'victim choices follow retained kills');
 let sent;app.post=async(url,body)=>{sent=body;return {queue:{items:[]},state:'idle'}};
 await app.startReel(false);assert.deepStrictEqual(Array.from(sent.items[0].weapons),['awp']);
 app.reel.weapons=['deagle'];app.recompute();assert.strictEqual(app.reel.items.length,0);
 app.reel.weapons=[];app.recompute();assert.strictEqual(app.reelEstimate.seconds,21);
 app.reel.weapons=['awp'];app.reel.content='kills';app.recompute();assert.strictEqual(app.reelEstimate.seconds,33);
}
main().catch(e=>{console.error(e);process.exitCode=1});
'''
    result=subprocess.run(['node','-',str(Path(__file__).parents[1]/'povforge/gui/static/app.js')],
        input=script,text=True,encoding='utf-8',capture_output=True)
    assert result.returncode==0,result.stderr
