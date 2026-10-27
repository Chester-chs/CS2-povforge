import os
from pathlib import Path

import pytest

from povforge import cdp
from test_workspace_browser import workspace_site


@pytest.mark.skipif(cdp.find_browser() is None,reason='Edge/Chrome required')
def test_profiles_preflight_diagnostics_and_quality_journey(workspace_site):
    url,state=workspace_site
    state['library']={'items':[{'path':'C:/Videos/A.mp4','name':'Test video','players':['Example'],
        'mode':'kill_events','size':1024,'mtime':1792600000,'duration':30,'missing':False,
        'quality':{'state':'warning','sampled':False,'checked_seconds':30,
                   'issues':[{'kind':'black','at':5,'end':9}]}}],'free_bytes':10*1024**3}
    with cdp.Browser(size=(1920,1080)) as browser:
        page=browser.page()
        try:
            page.call('Page.enable')
            page.call('Emulation.setDeviceMetricsOverride',width=1920,height=1080,deviceScaleFactor=1,mobile=False)
            page.call('Page.navigate',url=url)
            assert page.wait_for("document.querySelectorAll('.demo-card').length===5",15)
            page.evaluate("window.app=Alpine.$data(document.body)")
            assert page.evaluate("!!document.querySelector('.record-profiles')"), 'Recording presets need an actual visible control'
            page.evaluate("app.prefs.record_fps=120;app.profileName='AWP 120';app.reel.weapons=['awp'];app.openReel(false,'kill_events')")
            page.evaluate("document.querySelector('.profile-save').click()")
            assert page.wait_for("app.prefs.record_profiles?.length===1",4)
            assert state['prefs']['record_profiles'][0]['mode']=='kill_events'
            page.evaluate("app.prefs.record_fps=30;app.openMatchMode();app.profileSelected='AWP 120';app.applyRecordingProfile()",await_promise=True)
            assert page.wait_for("app.reelOpen && app.reel.content==='kill_events' && app.prefs.record_fps===120",3)
            assert page.evaluate("app.prefs.output")=='C:/Videos'
            assert state.get('submitted',[])==[]
            state['preflight']={'ok':False,'checks':[{'key':'destination','state':'error','reason':'not_writable','free_bytes':None}]}
            page.evaluate("app.startReel(false)",await_promise=True)
            assert state.get('submitted',[])==[]
            assert page.wait_for("document.querySelector('.record-checks')?.textContent.includes('无法写入')",3)
            for theme in ('light','dark'):
                page.evaluate(f"app.prefs.appearance='{theme}';app.applyTheme()")
                assert page.wait_for("document.querySelector('.record-checks')?.checkVisibility()",3)
                if os.environ.get('POVFORGE_TOOLS_SHOTS'):
                    folder=Path(os.environ['POVFORGE_TOOLS_SHOTS']);folder.mkdir(parents=True,exist_ok=True)
                    page.screenshot(folder/f'checks-{theme}.png')
            page.evaluate("app.openSettings();app.settingsTab='general'",await_promise=True)
            page.evaluate("document.querySelector('.diagnostics-export').click()")
            assert page.wait_for("app.diagnosticsPath.includes('PovForge-diagnostics')",3)
            assert state.get('diagnostic_exports')==1
            page.evaluate("app.openVideos()",await_promise=True)
            assert page.wait_for("document.querySelector('.video-quality')?.textContent.includes('疑似')",3)
            page.evaluate("document.querySelector('.quality-check').click()")
            assert page.wait_for("app.libraryVideos[0]?.quality?.state==='checking'",3)
            # Wait for the check submission before delivering its completed
            # report. Otherwise its delayed reply can erase visible findings
            # between the following visibility assertion and click.
            page.evaluate('app.loadVideos()',await_promise=True)
            assert page.wait_for("app.libraryVideos[0]?.quality?.state==='warning'",3)
            page.evaluate("document.querySelector('.video-actions button').click()")
            assert page.wait_for("document.querySelector('.quality-issue')?.checkVisibility()",3)
            page.evaluate("document.querySelector('.quality-issue').click()")
            assert page.wait_for('app.playerSeek===5',3)
            for theme in ('light','dark'):
                page.evaluate(f"app.prefs.appearance='{theme}';app.applyTheme()")
                if os.environ.get('POVFORGE_TOOLS_SHOTS'):
                    page.screenshot(folder/f'quality-{theme}.png')
            page.call('Emulation.setDeviceMetricsOverride',width=900,height=812,deviceScaleFactor=1,mobile=False)
            assert page.wait_for('document.documentElement.scrollWidth<=900',3)
            assert state.get('checked')==['C:/Videos/A.mp4']
        finally:
            page.close()
