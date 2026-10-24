"""Audit every visible text node across app views, without any recording call."""
import json

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
            page.evaluate('window.app=Alpine.$data(document.body)')
            views=[
                ('Demo library','app.openMatchMode()', '.library'),
                ('Setup','app.openSetup()', '.page.narrow'),
                ('Whole match',"app.openMatchMode();await app.pickDemo('C:/Demos/match-0.dem');app.player=app.demo.teams[0].players[0];app.setCustom(true)", '.match'),
                *[(mode,f"app.openReel(true,{json.dumps(mode)})",'.reel') for mode in ('kill_events','kills_deaths','duel','kills')],
                ('Video library','await app.openVideos()', '.finished-library'),
                *[(f'Settings {tab}',f"await app.openSettings();app.settingsTab={json.dumps(tab)}",'.settings-page') for tab in ('appearance','general','about')],
                ('Update dialog',"app.updateOpen=true;app.upd={state:'available',info:{version:'test',setup:'test',notes:'Release details'},can_install:true};app.job.state='running'",'.update-sheet'),
                ('Reference dialog',"app.updateOpen=false;app.job.state='idle';app.referenceWizard.open=true",'.reference-sheet'),
                ('Offline dialog',"app.referenceWizard.open=false;app.offline=true",'.sheet-backdrop'),
            ]
            for theme,system in [('light','light'),('dark','dark'),('auto','dark'),('auto','light')]:
                page.call('Emulation.setEmulatedMedia',features=[{'name':'prefers-color-scheme','value':system}])
                page.evaluate(f"(async()=>{{app.offline=false;await app.setAppearance({json.dumps(theme)});document.documentElement.dataset.expectedText={json.dumps('rgb(0, 0, 0)' if system=='light' else 'rgb(255, 255, 255)')}}})()",await_promise=True)
                for name,action,_ in views:
                    page.evaluate(f'(async()=>{{{action};await Alpine.nextTick()}})()',await_promise=True)
                    result=page.evaluate(AUDIT)
                    assert result['count']>15,(theme,name,result)
                    assert not result['bad'],(theme,system,name,result['bad'][:12])
                page.evaluate('app.offline=false;app.updateOpen=false;app.referenceWizard.open=false')
        finally:
            page.close()
