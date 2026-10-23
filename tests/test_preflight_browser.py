import pytest

from povforge import cdp
from test_workspace_browser import workspace_site


@pytest.mark.skipif(cdp.find_browser() is None, reason='Edge/Chrome required')
def test_preflight_weapons_and_finished_library_are_visible_and_responsive(workspace_site):
    url, _ = workspace_site
    with cdp.Browser(size=(1920,1080)) as browser:
        page = browser.page()
        try:
            page.call('Page.enable')
            page.call('Emulation.setDeviceMetricsOverride',width=1920,height=1080,deviceScaleFactor=1,mobile=False)
            page.call('Page.addScriptToEvaluateOnNewDocument', source="window.uiErrors=[];window.addEventListener('error',e=>uiErrors.push(e.message))")
            page.call('Page.navigate', url=url)
            assert page.wait_for("document.querySelectorAll('.demo-card').length===5", 15)
            page.evaluate("window.app=Alpine.$data(document.body);app.pickDemo('C:/Demos/match-0.dem')", await_promise=True)
            page.evaluate("app.player=app.demo.teams[0].players[0]")
            assert page.wait_for("document.querySelector('.match .preflight')?.textContent.includes('0:43')", 4)
            assert 'AK-47' in page.evaluate("document.querySelector('.match .round-events').textContent")
            page.evaluate("app.openReel(true,'kill_events')")
            assert page.wait_for("document.querySelector('.reel .weapon-details')?.textContent.includes('M4A4')", 4)
            assert page.evaluate("document.querySelector('.reel .preflight').textContent.includes('主体画面')")
            page.evaluate("document.querySelector('.videos-nav').click()")
            assert page.wait_for("document.querySelectorAll('.video-row').length===1", 4)
            assert page.evaluate("document.querySelector('.finished-library').getBoundingClientRect().width>900")
            page.evaluate("window.opened=[];app.openPath=(path,select)=>opened.push({path,select});document.querySelector('.video-actions button').click()")
            assert page.evaluate('opened[0].path') == 'C:/Videos/A.mp4'
            page.evaluate("app.videoQuery='no-match'")
            assert page.wait_for("document.querySelectorAll('.video-row').length===0", 3)
            page.evaluate("app.videoQuery='';app.lang='en'")
            assert page.wait_for("document.querySelector('.finished-library h1').textContent==='Video library'", 3)
            page.call('Emulation.setDeviceMetricsOverride',width=900,height=812,deviceScaleFactor=1,mobile=False)
            assert page.wait_for('document.documentElement.scrollWidth<=900',3)
            page.evaluate("app.openMatchMode()")
            assert page.wait_for("document.querySelector('.library').getBoundingClientRect().height>0",3)
            assert page.evaluate('uiErrors') == []
        finally:
            page.close()
