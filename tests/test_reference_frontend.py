"""Exercise the actual Alpine component as plain JS, without launching a browser."""
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from povforge import effects


@pytest.mark.skipif(not shutil.which("node"), reason="Node required")
def test_targeted_proposal_needs_apply_is_editable_and_survives_reload():
    path = Path(__file__).parents[1] / "povforge/gui/static/app.js"
    script = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
let factory;
const context = { document: { addEventListener: (_, fn) => fn() },
  Alpine: { data: (_, fn) => factory = fn }, setTimeout, clearTimeout };
vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), context);
async function test() {
  const defaults = DEFAULTS;
  const app = factory();
  app.fxMeta.defaults = defaults;
  app.fx = { ...defaults, music: 'song.wav', music_sync: true };
  app.saveFx = () => {};
  app.closeReference = () => {};
  app.post = async () => ({proposal: {status:'detected', patch:{kill_flash:true}}});
  app.referenceWizard = {id:'sample', title:'Example', busy:false, start:0, end:5, kind:'flash', description:'flash'};
  await app.proposeReference();
  assert.strictEqual(app.fx.kill_flash, false, 'analysis must not apply');
  app.applyReferenceProposal();
  assert.strictEqual(app.fx.kill_flash, true);
  assert.strictEqual(app.fx.music, 'song.wav');
  assert.strictEqual(app.fx.music_sync, true);
  assert.notStrictEqual(app.partNow('kills'), '', 'active effect must have an editable option');
  const saved = { ...app.fx };
  app.pickPart('kills', '');
  assert.strictEqual(app.fx.kill_flash, false, 'effect can be turned off');
  const reloaded = factory();
  reloaded.get = async () => ({ prefs:{reel_fx:saved}, effects:{defaults}, setup:{}, job:{}, queue:{} });
  await reloaded.refresh();
  assert.strictEqual(reloaded.fx.kill_flash, true, 'unnamed selected effect must survive reload');
  assert.strictEqual(reloaded.fx.music_sync, true);
  assert.notStrictEqual(reloaded.partNow('kills'), '');
}
test().catch(e => { console.error(e); process.exitCode = 1; });
'''.replace("DEFAULTS", json.dumps(effects.DEFAULTS))
    result = subprocess.run(["node", "-", str(path)], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
