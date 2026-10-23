import shutil
import subprocess
from pathlib import Path
import pytest


@pytest.mark.skipif(not shutil.which('node'), reason='Node required')
def test_event_modes_chronology_opponent_swap_and_queue_payload():
    script = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
let factory;
vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), {
  document:{addEventListener:(_,fn)=>fn()}, Alpine:{data:(_,fn)=>factory=fn}, setTimeout, clearTimeout
});
async function test() {
  const app=factory(); app.lang='en'; app.toast=()=>{};
  const a={steamid:'a', name:'A', rounds_k:[1,0,3], rounds_died:[true,true,false]};
  const b={steamid:'b', name:'B', rounds_k:[0,1,0], rounds_died:[true,false,false]};
  const c={steamid:'c', name:'Teammate', rounds_k:[0,0,0]};
  const info={map_pretty:'Dust II',teams:[{players:[a,c]},{players:[b]}],duels:[
    {round:1,tick:100,attacker:'a',victim:'b'}, {round:2,tick:300,attacker:'b',victim:'a'}]};
  const src={path:'match.dem',info,steamid:'a',opponent:'b'};
  app.reel.sources=[src]; app.reel.steamid='a';
  app.setReelContent('kills_deaths');
  assert.deepStrictEqual(Array.from(app.reel.items,x=>x.round),[1,2,3]);
  assert.strictEqual(app.reel.items[1].died,true);
  app.moveReelItem(0,1);
  assert.strictEqual(app.reel.items[0].round,1,'event chronology cannot be reordered');
  app.setReelContent('kill_events');
  assert.deepStrictEqual(Array.from(app.reel.items,x=>x.round),[1,3]);
  app.setReelContent('duel');
  assert.deepStrictEqual(Array.from(app.duelOpponents(src),p=>p.steamid),['b']);
  assert.deepStrictEqual(Array.from(app.reel.items,x=>x.round),[1,2]);
  assert.ok(app.reel.items.every(x=>x.opponent==='b'));
  app.swapDuel(src);
  assert.strictEqual(app.srcPlayerId(src),'b');
  assert.strictEqual(src.opponent,'a');
  assert.ok(app.reel.items.every(x=>x.steamid==='b' && x.opponent==='a'));
  let payload; app.post=async(url,body)=>{payload=body;return {queue:{}}};
  app.fx={camera:{victim:true}};
  await app.startReel(false);
  assert.ok(payload.items.every(x=>x.mode==='duel' && x.opponent==='a'));
  assert.strictEqual(payload.effects.camera.victim,false,'duels already include both views');
  app.setReelContent('kills');
  app.reel.steamid='a'; src.steamid='a'; app.recompute();
  assert.deepStrictEqual(Array.from(app.reel.items,x=>x.round),[3],'default highlights stay intact');
}
test().catch(e=>{console.error(e);process.exitCode=1});
'''
    result = subprocess.run(['node', '-', str(Path(__file__).parents[1] / 'povforge/gui/static/app.js')],
                            input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
