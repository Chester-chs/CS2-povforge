"""Audit every visible text node across app views, without any recording call."""
import json
import os
from pathlib import Path

import pytest

from povforge import cdp
from test_workspace_browser import workspace_site


AUDIT = r'''(() => {
 const expected=document.documentElement.dataset.expectedText;
 const rows=[],bad=[];
 const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
 let node;
 while(node=walker.nextNode()) {
   const el=node.parentElement,text=node.textContent.trim();
   if(!text || !el || el.closest('svg,script,style') || !el.checkVisibility() || !el.getBoundingClientRect().height)continue;
   const style=getComputedStyle(el);let opacity=1;
   for(let p=el;p;p=p.parentElement)opacity*=Number(getComputedStyle(p).opacity);
   const row={text:text.slice(0,70),color:style.color,opacity};rows.push(row);
   if(row.color!==expected || opacity!==1)bad.push(row);
 }
 for(const el of document.querySelectorAll('input[placeholder],textarea[placeholder]')){
   if(!el.checkVisibility() || !el.getBoundingClientRect().height)continue;
   const s=getComputedStyle(el,'::placeholder');
   if(s.color!==expected || Number(s.opacity)!==1)bad.push({placeholder:el.placeholder,color:s.color,opacity:s.opacity});
 }
 return {count:rows.length,bad};
})()'''


@pytest.mark.skipif(cdp.find_browser() is None,reason='Edge/Chrome required')
def test_black_white_text_across_all_pages_and_dialogs(workspace_site):
    url,_=workspace_site
    with cdp.Browser(size=(1264,812)) as browser:
        page=browser.page()
        try:
            page.call('Page.enable');page.call('Page.navigate',url=url)
            assert page.wait_for("document.querySelectorAll('.demo-card').length===5",15)
            # Freeze only background health/job polling after boot. Otherwise a
            # successful tick clears the intentionally simulated offline state.
            # View-specific reads and real Alpine rendering still run normally.
            page.evaluate("window.app=Alpine.$data(document.body);window.originalGet=app.get.bind(app);app.get=p=>['/api/state','/api/job'].includes(p)?new Promise(()=>{}):originalGet(p)")
            views=[
                ('Demo library','app.openMatchMode()', '.library'),
                ('Setup','app.openSetup()', '.page.narrow'),
                ('Whole match',"app.openMatchMode();await app.pickDemo('C:/Demos/match-0.dem');app.player=app.demo.teams[0].players[0];app.setCustom(true)", '.match'),
                *[(mode,f"app.openReel(true,{json.dumps(mode)})",'.reel') for mode in ('kill_events','kills_deaths','duel','kills')],
                ('Video library','await app.openVideos()', '.finished-library'),
                ('Quality results',"app.libraryVideos[0].quality={state:'warning',issues:[{at:5,kind:'black'}]};await app.playVideo(app.libraryVideos[0])",'.quality-details'),
                ('Library player',"await app.playVideo(app.libraryVideos[0]);app.playerEvents=[{at:1,kind:'kill',round:1,weapon:'awp',player:'Example'}]",'.video-player'),
                ('Close player','app.closeVideo()', '.finished-library'),
                *[(f'Settings {tab}',f"await app.openSettings();app.settingsTab={json.dumps(tab)}",'.settings-page') for tab in ('appearance','general','about')],
                ('Preflight and profiles',"app.openMatchMode();app.recordChecks={at:'12:00',checks:[{key:'output',reason:'not_writable',state:'error'}]};document.querySelector('.profile-create').open=true;app.profileName='Test profile'",'.record-checks'),
                ('Recording progress',"app.videosOpen=false;app.settingsOpen=false;app.setupOpen=false;app.showRun=true;app.job={...app.job,state:'running',stage:'record',kind:'match',recorded:[1],planned:[1,2],step:[1,2],elapsed:5,player:'Example',item:1};app.queue={items:[{id:1,state:'running',name:'Example',map:'Dust2',rounds:[1,2],kind:'match'}],paused:false}",'.run'),
                ('Recording error',"app.job.state='error';app.job.error='Test error';app.queue.items[0].state='error'",'.run'),
                ('Update dialog',"app.showRun=false;app.updateOpen=true;app.upd={state:'available',info:{version:'test',setup:'test',notes:'Release details'},can_install:true};app.job.state='running'",'.update-sheet'),
                ('Reference dialog',"app.updateOpen=false;app.job.state='idle';app.referenceWizard.open=true",'.reference-sheet'),
                ('Offline dialog',"app.referenceWizard.open=false;app.offline=true",'.sheet-backdrop[x-show^="offline"]'),
            ]
            for theme,system in [('light','light'),('dark','dark'),('auto','dark'),('auto','light')]:
                page.call('Emulation.setEmulatedMedia',features=[{'name':'prefers-color-scheme','value':system}])
                page.evaluate(f"(async()=>{{app.job.state='idle';app.offline=false;await app.setAppearance({json.dumps(theme)});document.documentElement.dataset.expectedText={json.dumps('rgb(0, 0, 0)' if system=='light' else 'rgb(255, 255, 255)')}}})()",await_promise=True)
                for name,action,target in views:
                    page.evaluate(f'(async()=>{{{action};await Alpine.nextTick()}})()',await_promise=True)
                    assert page.wait_for(f'document.querySelector({json.dumps(target)})?.checkVisibility()',3),(theme,name)
                    result=page.evaluate(AUDIT)
                    assert result['count']>15,(theme,name,result)
                    assert not result['bad'],(theme,system,name,result['bad'][:12])
                    if os.environ.get('POVFORGE_THEME_SHOTS') and (name.startswith('Settings') or name=='Video library'):
                        folder=Path(os.environ['POVFORGE_THEME_SHOTS']);folder.mkdir(parents=True,exist_ok=True)
                        page.screenshot(folder/f'{theme}-{system}-{name.replace(" ","-")}.png')
                page.evaluate('app.offline=false;app.updateOpen=false;app.referenceWizard.open=false')
        finally:
            page.close()


@pytest.mark.skipif(cdp.find_browser() is None,reason='Edge/Chrome required')
def test_primary_button_text_stays_readable_for_all_accent_colors(workspace_site):
    url,_=workspace_site
    with cdp.Browser(size=(1264,812)) as browser:
        page=browser.page()
        try:
            page.call('Page.enable');page.call('Page.navigate',url=url)
            assert page.wait_for("document.querySelectorAll('.demo-card').length===5",15)
            page.evaluate("window.app=Alpine.$data(document.body);app.openSettings();app.settingsTab='about'",await_promise=True)
            for theme in ('light','dark'):
                page.evaluate(f'app.setAppearance({json.dumps(theme)})',await_promise=True)
                for accent in ('blue','purple','pink','red','orange','yellow','green','graphite'):
                    page.evaluate(f"app.prefs.accent={json.dumps(accent)};app.applyTheme()")
                    ratio=page.evaluate(r'''(() => {
                      const el=document.querySelector('.about-page .btn.primary');
                      const canvas=document.createElement('canvas');canvas.width=canvas.height=1;
                      const ctx=canvas.getContext('2d',{willReadFrequently:true});
                      ctx.fillStyle='#fff';ctx.fillRect(0,0,1,1);
                      let chain=[];for(let p=el;p;p=p.parentElement)chain.unshift(p);
                      for(const p of chain){ctx.fillStyle=getComputedStyle(p).backgroundColor;ctx.fillRect(0,0,1,1)}
                      const bg=ctx.getImageData(0,0,1,1).data.slice(0,3);
                      ctx.fillStyle=getComputedStyle(el).color;ctx.fillRect(0,0,1,1);
                      const fg=ctx.getImageData(0,0,1,1).data.slice(0,3);
                      const lum=c=>Array.from(c,(x,i)=>{x/=255;return(x<=.04045?x/12.92:((x+.055)/1.055)**2.4)*[.2126,.7152,.0722][i]}).reduce((a,b)=>a+b,0);
                      const a=lum(bg),b=lum(fg);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
                    })()''')
                    assert ratio>=4.5,(theme,accent,ratio)
        finally:
            page.close()
