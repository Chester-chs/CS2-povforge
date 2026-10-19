"""Screenshot of the FACEIT match room, taken automatically for the intro.

FACEIT demo files are named after the match (``1-<uuid>-1-1.dem.zst``), and
the match room page is public, so no login is needed. The page is opened in a
headless copy of the Edge or Chrome already on the PC (driven directly through
its DevTools protocol, see cdp.py), the cookie-consent banner is hidden
(nothing is accepted), and the scoreboard is saved as an image.
"""

from __future__ import annotations

import datetime
import json
import re
import time
from pathlib import Path

MATCH_ID = re.compile(r"1-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)

# The consent banner (Usercentrics) lives in a shadow root under this element.
CONSENT_SELECTORS = ["#usercentrics-cmp-ui", "#usercentrics-root", "#onetrust-consent-sdk"]

_HIDE_JS = """
(sels) => {
  for (const s of sels) document.querySelectorAll(s).forEach(e => e.remove());
  for (const e of [document.documentElement, document.body]) if (e) e.style.overflow = 'auto';
}
"""

_INIT_CSS = ", ".join(CONSENT_SELECTORS) + " { display: none !important; }"
_INIT_JS = f"""
document.addEventListener('DOMContentLoaded', () => {{
  const st = document.createElement('style');
  st.textContent = {_INIT_CSS!r};
  document.head.appendChild(st);
}});
"""

# The match header has loaded once the page text has "Matchroom" plus the
# result ("WINNER") or the stats tabs ("SUMMARY"). ("VS" is an image, not text.)
_READY_JS = """() => {
  const t = document.body ? document.body.innerText : '';
  return /Matchroom/i.test(t) && /\\b(WINNER|SUMMARY|SCOREBOARD)\\b/i.test(t);
}"""

# The scoreboard: the smallest element holding both teams' tables ("Team avg"
# appears once per team). Class names on the page are generated, so we go by text.
# Fixed/sticky bars (the "Matchroom" header) would cover it, so they are hidden.
_TABLES_JS = """() => {
  const els = [...document.querySelectorAll('body *')].filter(e => {
    const t = e.innerText || '';
    return (t.match(/Team avg/g) || []).length >= 2 && /MVPs/.test(t);
  });
  if (!els.length) return false;
  els.sort((a, b) => a.innerText.length - b.innerText.length);
  const target = els[0];
  document.querySelectorAll('[data-povforge-shot]').forEach(e => e.removeAttribute('data-povforge-shot'));
  target.setAttribute('data-povforge-shot', '1');
  for (const e of document.querySelectorAll('body *')) {
    const pos = getComputedStyle(e).position;
    // only bars outside the tables; the tables' own sticky columns (player names) must stay
    if ((pos === 'fixed' || pos === 'sticky') && !e.contains(target) && !target.contains(e)) e.style.visibility = 'hidden';
  }
  return true;
}"""


# Match details from the JSON the match room page itself loads (no login needed).
_MATCH_JS = """async (mid) => {
  try {
    const r = await fetch('/api/match/v2/match/' + mid, {credentials: 'omit'});
    const p = (await r.json()).payload || {};
    return {startedAt: p.startedAt || null, finishedAt: p.finishedAt || null, createdAt: p.createdAt || null};
  } catch (e) { return null; }
}"""


def match_time(info: dict, tz: str = "") -> "datetime.datetime | None":
    """Match start as a local time (``tz`` = IANA name, empty = this PC's zone)."""
    raw = info.get("startedAt") or info.get("createdAt")
    if not raw:
        return None
    t = datetime.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=datetime.timezone.utc)
    if tz:
        from zoneinfo import ZoneInfo
        return t.astimezone(ZoneInfo(tz))
    return t.astimezone()


def match_id(name: str | Path) -> str | None:
    """The FACEIT match id in a demo file name, or None."""
    m = MATCH_ID.search(Path(name).name)
    return m.group(0).lower() if m else None


def room_url(mid: str) -> str:
    return f"https://www.faceit.com/en/cs2/room/{mid}/scoreboard"


def screenshot_room(mid: str, out: Path, size: tuple[int, int] = (1920, 1080),
                    timeout: float = 45.0, headless: bool = True, url: str | None = None,
                    zoom: float = 1.2, info_out: Path | None = None) -> Path:
    """Save a screenshot of the match room to ``out``; raises on failure.

    With ``info_out``, the match times (``startedAt``, ``finishedAt``, UTC)
    are saved there as JSON, read from the same public data the page uses.

    The page is laid out at ``size / zoom`` and rendered at ``zoom``x, so the
    image is ``size`` pixels with slightly larger, sharp text.
    """
    from .cdp import Browser

    url = url or room_url(mid)
    view = (round(size[0] / zoom), round(size[1] / zoom))
    with Browser(headless=headless, size=view) as browser:
        page = browser.page()
        try:
            # Headless browsers announce themselves in the user agent; use the normal one.
            ua = str(page.evaluate("navigator.userAgent")).replace("HeadlessChrome", "Chrome")
            page.call("Network.enable")
            page.call("Network.setUserAgentOverride", userAgent=ua, acceptLanguage="en-US")
            page.call("Emulation.setDeviceMetricsOverride", width=view[0], height=view[1],
                      deviceScaleFactor=zoom, mobile=False)
            page.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "dark"}])
            page.call("Page.enable")
            page.call("Page.addScriptToEvaluateOnNewDocument", source=_INIT_JS)
            page.call("Page.navigate", url=url)
            if not page.wait_for(f"({_READY_JS})()", timeout):
                # keep what the browser saw, to find out why
                failed = out.with_name(out.stem + "_failed.png")
                text = title = ""
                try:
                    page.evaluate(f"({_HIDE_JS})({json.dumps(CONSENT_SELECTORS)})")
                    out.parent.mkdir(parents=True, exist_ok=True)
                    page.screenshot(failed)
                    title = page.evaluate("document.title") or ""
                    text = " ".join((page.evaluate("document.body ? document.body.innerText : ''") or "").split())[:160]
                except Exception:
                    pass
                raise RuntimeError(f"the match room did not load; what the browser saw: {failed} "
                                   f"(page title '{title}', text '{text}')")
            time.sleep(3.0)                     # let pictures and avatars finish
            page.evaluate(f"({_HIDE_JS})({json.dumps(CONSENT_SELECTORS)})")
            out.parent.mkdir(parents=True, exist_ok=True)
            if info_out is not None:
                info = page.evaluate(f"({_MATCH_JS})({json.dumps(mid)})", await_promise=True)
                if info:
                    info_out.write_text(json.dumps(info, indent=2), encoding="utf-8")
            # the stats tables load a moment after the header
            if page.wait_for(f"({_TABLES_JS})()", 15):
                time.sleep(1.0)                 # avatars
                box = page.evaluate("""(() => {
                    const e = document.querySelector('[data-povforge-shot]');
                    e.scrollIntoView({block: 'start'});
                    const r = e.getBoundingClientRect();
                    return {x: r.left + window.scrollX, y: r.top + window.scrollY, width: r.width, height: r.height};
                })()""")
                time.sleep(0.5)
                page.screenshot(out, clip=box)
            else:                               # no tables (e.g. match without stats): the top of the page
                page.evaluate("window.scrollTo(0, 0)")
                page.screenshot(out)
        finally:
            page.close()
    return out
