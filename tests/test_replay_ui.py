def test_style_actions_preserve_the_independent_victim_choice():
    """A style must neither enable extra victim recording nor undo an opt-in."""
    import json
    import shutil
    import subprocess
    from pathlib import Path

    import pytest

    node = shutil.which("node")
    if not node:
        pytest.skip("needs Node")
    script = """
const fs = require('fs'), vm = require('vm');
let app;
vm.runInNewContext(fs.readFileSync(process.argv[1], 'utf8'), {
  document: {addEventListener: (_, f) => f()},
  Alpine: {data: (_, make) => app = make()},
  navigator: {language: 'en'}, Intl, console, setTimeout: () => 0, clearTimeout: () => {}
});
app.fxMeta = {defaults: {intro:'none',outro:'none',transition:'cut',grade:'none',
  camera:{mode:'pov',follow:false,orbit:false,wide:false,victim:false,
    durations:{follow:1.5,orbit:1,wide:1.8,victim:1.2},frequency:0.5}}};
app.lang = 'en';
app.post = async (_, body) => ({...app.prefs, ...body});
(async () => {
  const states = [];
  for (const victim of [false, true]) for (const mode of ['pov','reference']) {
    const camera = {...app.cameraSettings(), mode:'reference',follow:true,victim:!victim};
    app.styleRef = {effects:{camera},name:'reference',presetName:'saved'};
    app.prefs.fx_presets = [{name:'source',fx:{camera,transition:'flash',transition_seconds:0.3,transitions:{}}}];
    for (const action of ['import','mix','preset','plain','save']) {
      app.fx = {...app.fxDefaults(),camera:{...app.cameraSettings(),mode,victim,placement:'end',selected:['chosen-kill']}};
      if (action === 'import') app.applyRef();
      if (action === 'mix') {
        app.pickPart('transition','my:source');
        if (app.fx.transition !== 'flash' || app.fx.camera.victim !== victim) throw Error('Style mixing changed victim choice');
      }
      if (action === 'preset') app.applyPreset('my:source');
      if (action === 'plain') app.applyPreset('plain');
      if (action === 'save') await app.saveRefPreset();
      states.push({action,wantVictim:victim,wantMode:mode,got:app.fx.camera});
    }
  }
  app.fx = {...app.fxDefaults(),camera:{...app.cameraSettings(),victim:true}};
  const summary = app.fxSummary(app.fx);
  const withVictim = app.presetOf(app.fx);
  app.fx.camera.victim = false;
  const withoutVictim = app.presetOf(app.fx);
  app.fx = null;
  app.get = async () => ({effects:app.fxMeta,prefs:{fx_presets:[],reel_fx:{transition:'flash',
    camera:{...app.cameraSettings(),mode:'reference',victim:true}}}});
  await app.refresh();
  process.stdout.write(JSON.stringify({states,summary,withVictim,withoutVictim,restored:app.fx.camera,
    defaultVictim:app.cameraSettings().victim}));
})().catch(e => {console.error(e);process.exitCode=1;});
"""
    result = subprocess.run([node, "-e", script, str(Path("povforge/gui/static/app.js").resolve())],
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    for state in data["states"]:
        assert state["got"]["victim"] is state["wantVictim"], state
        assert state["got"]["mode"] == "pov", state
        assert state["got"]["placement"] == "end", state
        assert state["got"]["selected"] == ["chosen-kill"], state
    assert "victim" in data["summary"].lower()
    assert data["withVictim"] == data["withoutVictim"] == "plain"
    assert data["defaultVictim"] is False
    assert data["restored"]["mode"] == "pov"
    assert data["restored"]["victim"] is True
