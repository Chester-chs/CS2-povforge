"""Selected-round totals must follow player, round and duel selections."""
import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(not shutil.which('node'), reason='Node required')
def test_selected_kill_and_death_totals():
    script = r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
let factory;
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),{
 document:{addEventListener:(_,fn)=>fn()}, Alpine:{data:(_,fn)=>factory=fn},
 navigator:{language:'en'},window:{},setTimeout:()=>1,clearTimeout:()=>{}
});
const app=factory();
const a={steamid:'a',name:'A',rounds_k:[2,4],rounds_died:[false,true]};
const b={steamid:'b',name:'B',rounds_k:[1,2],rounds_died:[true,false]};
app.player=a;app.demo={rounds:2};app.customRounds=false;
assert.strictEqual(app.matchTotals.kills,6);assert.strictEqual(app.matchTotals.deaths,1);
app.customRounds=true;app.chosenRounds=[2];
assert.strictEqual(app.matchTotals.kills,4);assert.strictEqual(app.matchTotals.deaths,1);
app.chosenRounds=[];assert.strictEqual(app.matchTotals.kills,0);
const info={teams:[{players:[a,b]}],duels:[
 {round:1,tick:100,attacker:'a',victim:'b'},
 {round:2,tick:200,attacker:'b',victim:'a'}]};
app.reel.sources=[{path:'x.dem',info,steamid:'a',opponent:'b'}];
for(const mode of ['kill_events','kills_deaths']){
 app.reel.content=mode;app.reel.items=[{path:'x.dem',steamid:'a',round:2}];
 assert.strictEqual(app.reelTotals[0].kills,4);assert.strictEqual(app.reelTotals[0].deaths,1);
 app.reel.items=[];assert.strictEqual(app.reelTotals.length,0);
}
app.reel.content='duel';app.reel.items=[{path:'x.dem',steamid:'a',opponent:'b',round:1}];
assert.strictEqual(app.reelTotals.length,2);
assert.strictEqual(app.reelTotals[0].name,'A');
assert.strictEqual(app.reelTotals[0].kills,1);assert.strictEqual(app.reelTotals[0].deaths,0);
assert.strictEqual(app.reelTotals[1].kills,0);assert.strictEqual(app.reelTotals[1].deaths,1);
app.reel.items.push({...app.reel.items[0]});
assert.strictEqual(app.reelTotals[0].kills,1,'duplicate round must not inflate totals');
app.reel.items.push({path:'x.dem',steamid:'a',opponent:'b',round:2});
assert.strictEqual(app.reelTotals[0].deaths,1);
'''
    result = subprocess.run(['node', '-', str(Path(__file__).parents[1] / 'povforge/gui/static/app.js')],
                            input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
