import subprocess

import pytest

from povforge import cdp
from povforge.tools import find_ffmpeg
from test_workspace_browser import workspace_site


@pytest.mark.skipif(cdp.find_browser() is None or not find_ffmpeg(),reason='Browser and FFmpeg required')
def test_recovered_queue_weapon_ui_and_real_video_event_seeking(workspace_site,tmp_path):
    url,state=workspace_site
    media=tmp_path/'fixture.mp4'
    subprocess.run([find_ffmpeg(),'-y','-v','error','-f','lavfi','-i','testsrc2=s=320x180:r=24',
        '-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','4','-c:v','libx264','-preset','ultrafast',
        '-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(media)],check=True)
    state['media']=str(media)
    state['playback']={'src':'/test-media.mp4','name':'Example clip','events':[
        {'at':0,'kind':'round','round':1},{'at':1,'kind':'kill','round':1,'weapon':'awp','player':'A'},
        {'at':2.5,'kind':'death','round':1,'player':'A'}]}
    state['queue']={'items':[{'id':1,'kind':'match','name':'Saved player','rounds':[1],
        'map':'Dust2','state':'queued'}],'paused':True,'recovered':True,'save_error':''}
    with cdp.Browser(size=(1264,812)) as browser:
        page=browser.page()
        try:
            page.call('Page.enable')
            page.call('Page.addScriptToEvaluateOnNewDocument',source="window.uiErrors=[];window.addEventListener('error',e=>uiErrors.push(e.message))")
            page.call('Page.navigate',url=url)
            assert page.wait_for("document.querySelectorAll('.demo-card').length===5",15)
            assert page.wait_for("document.querySelector('.queue-recovered')?.checkVisibility()",3)
            page.evaluate("window.app=Alpine.$data(document.body);app.pickDemo('C:/Demos/match-0.dem')",await_promise=True)
            page.evaluate("app.player=app.demo.teams[0].players[0];app.openReel(true,'kill_events')")
            assert page.wait_for("document.querySelector('[data-weapon=ak47]')!==null",3)
            page.evaluate("document.querySelector('[data-weapon=ak47]').click()")
            assert page.wait_for("app.reel.items.length===1 && app.reelEstimate.seconds===13",3)
            assert 'M4A4' in page.evaluate("document.querySelector('.reel-list').textContent")
            page.evaluate("app.openVideos()",await_promise=True)
            page.evaluate("document.querySelector('.video-actions button').click()")
            assert page.wait_for("document.querySelector('.library-video')?.readyState>=2",10)
            assert page.evaluate("document.querySelectorAll('.player-event').length")==3
            page.evaluate("document.querySelector('.library-video').pause();document.querySelector('[data-event-kind=kill]').click()")
            assert page.wait_for("Math.abs(document.querySelector('.library-video').currentTime-1)<.15",4),page.evaluate("JSON.stringify({current:document.querySelector('.library-video').currentTime,duration:document.querySelector('.library-video').duration,paused:document.querySelector('.library-video').paused,seek:app.playerSeek,ref:!!app.$refs.libraryVideo,errors:uiErrors})")
            page.evaluate("document.querySelector('.event-next').click()")
            assert page.wait_for("Math.abs(document.querySelector('.library-video').currentTime-2.5)<.15",4)
            page.evaluate("document.querySelector('.event-prev').click()")
            assert page.wait_for("Math.abs(document.querySelector('.library-video').currentTime-1)<.15",4)
            page.evaluate("app.lang='en';app.prefs.appearance='dark';app.applyTheme()")
            assert page.wait_for("getComputedStyle(document.querySelector('.player-event span')).color==='rgb(255, 255, 255)'",3)
            page.evaluate("app.openMatchMode()")
            assert page.wait_for("document.querySelector('.library-video')===null",3)
            assert page.evaluate('uiErrors')==[]
        finally:
            page.close()
