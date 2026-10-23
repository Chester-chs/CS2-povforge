"""The real frontend must authenticate both normal writes and window closure."""

from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.skipif(not shutil.which('node'), reason='Node required')
def test_posts_and_pagehide_use_bootstrapped_token():
    script = r'''
const fs = require('fs'), vm = require('vm'), assert = require('assert');
let factory, pagehide;
const requests = [];
vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), {
  document: { addEventListener: (_, fn) => fn(), querySelector: () => ({content:'session-token'}),
    getElementById: () => ({}), documentElement: {} },
  Alpine: { data: (_, fn) => factory = fn },
  navigator: { language:'en' }, window: { addEventListener: (name, fn) => { if(name === 'pagehide') pagehide=fn; } },
  setTimeout: () => 1, clearTimeout: () => {},
  fetch: async (url, opts={}) => { requests.push({url,opts}); return {ok:true,json:async()=>({ok:true}),text:async()=>''}; }
});
async function test() {
  const app = factory();
  app.refresh = async () => {}; app.applyTheme = () => {}; app.loadDemos = () => {}; app.$watch = () => {};
  Object.defineProperty(app, 'ready', {value:true});
  await app.boot();
  await app.post('/api/prefs', {lang:'en'});
  const write = requests.find(r => r.url === '/api/prefs');
  assert.strictEqual(write.opts.headers['X-Povforge-Token'], 'session-token');
  assert.strictEqual(write.opts.method, 'POST');
  assert.deepStrictEqual(JSON.parse(write.opts.body), {lang:'en'});
  assert.ok(pagehide, 'boot must register closure notification');
  pagehide();
  const bye = requests.find(r => r.url === '/api/bye');
  assert.strictEqual(bye.opts.headers['X-Povforge-Token'], 'session-token');
  assert.strictEqual(bye.opts.keepalive, true);
  assert.strictEqual(bye.opts.method, 'POST');
}
test().catch(e => {console.error(e); process.exitCode=1});
'''
    path = Path(__file__).parents[1] / 'povforge/gui/static/app.js'
    result = subprocess.run(['node', '-', str(path)], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
