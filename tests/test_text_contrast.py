"""Check actual rendered helper text, including alpha and ancestor surfaces."""
import json
import os

import pytest

from povforge import cdp
from test_workspace_browser import workspace_site


MEASURE = r'''(() => {
 const rgba = s => (s.match(/[\d.]+/g) || []).map(Number);
 const over = (fg,bg) => { const a=fg[3] ?? 1;return fg.slice(0,3).map((v,i)=>v*a+bg[i]*(1-a)); };
 const background = el => {
   let nodes=[];for(let n=el;n;n=n.parentElement)nodes.unshift(n);
   return nodes.reduce((bg,n)=>over(rgba(getComputedStyle(n).backgroundColor),bg),[255,255,255]);
 };
 const luminance = rgb => rgb.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4})
   .reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
 const ratio = el => {
   const bg=background(el), fg=over(rgba(getComputedStyle(el).color),bg);
   const a=luminance(fg),b=luminance(bg);
   return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
 };
 return Array.from(document.querySelectorAll('.preflight h3,.preflight .hint,.reel-totals p,.reel .group-title .hint,.weapon-details summary,.video-row small,.finished-library .footnote'))
   .filter(el=>el.getBoundingClientRect().height>0 && el.checkVisibility())
   .map(el=>({text:el.textContent.slice(0,80),ratio:ratio(el)}));
})()'''


@pytest.mark.skipif(cdp.find_browser() is None, reason='Edge/Chrome required')
def test_readable_secondary_text_in_light_dark_and_system_themes(workspace_site):
    url, _ = workspace_site
    with cdp.Browser(size=(1264,812)) as browser:
        page=browser.page()
        try:
            page.call('Page.enable')
            page.call('Page.navigate',url=url)
            assert page.wait_for("document.querySelectorAll('.demo-card').length===5",15)
            page.evaluate("window.app=Alpine.$data(document.body);app.pickDemo('C:/Demos/match-0.dem')",await_promise=True)
            page.evaluate("app.player=app.demo.teams[0].players[0];app.openReel(true,'kill_events')")
            assert page.wait_for("document.querySelector('.reel .preflight')?.checkVisibility()",4)
            reports=[]
            for theme,system in [('light','light'),('dark','dark'),('auto','dark'),('auto','light')]:
                page.call('Emulation.setEmulatedMedia',features=[{'name':'prefers-color-scheme','value':system}])
                page.evaluate(f"app.setAppearance({json.dumps(theme)})",await_promise=True)
                rows=page.evaluate(MEASURE)
                assert len(rows)>=5
                reports.append({'theme':theme,'system':system,'samples':rows})
                assert all(r['ratio']>=4.5 for r in rows),reports[-1]
            page.evaluate('app.openVideos()',await_promise=True)
            assert page.wait_for("document.querySelector('.video-row')?.checkVisibility()",4)
            for theme in ('light','dark'):
                page.evaluate(f"app.setAppearance({json.dumps(theme)})",await_promise=True)
                rows=page.evaluate(MEASURE)
                assert len(rows)>=4
                reports.append({'library':theme,'samples':rows})
                assert all(r['ratio']>=4.5 for r in rows),reports[-1]
            if os.environ.get('POVFORGE_CONTRAST_REPORT'):
                from pathlib import Path
                Path(os.environ['POVFORGE_CONTRAST_REPORT']).write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
        finally:
            page.close()
