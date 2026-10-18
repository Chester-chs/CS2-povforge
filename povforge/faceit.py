"""Screenshot of the FACEIT match room, taken automatically for the intro.

FACEIT demo files are named after the match (``1-<uuid>-1-1.dem.zst``), and
the match room page is public, so no login is needed. The page is opened in a
headless browser (Playwright, using the Edge or Chrome already on the PC), the
cookie-consent banner is hidden (nothing is accepted), and the visible part of
the page is saved as an image.
"""

from __future__ import annotations

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
    if ((pos === 'fixed' || pos === 'sticky') && !e.contains(target)) e.style.visibility = 'hidden';
  }
  return true;
}"""


def match_id(name: str | Path) -> str | None:
    """The FACEIT match id in a demo file name, or None."""
    m = MATCH_ID.search(Path(name).name)
    return m.group(0).lower() if m else None


def room_url(mid: str) -> str:
    return f"https://www.faceit.com/en/cs2/room/{mid}/scoreboard"


def _launch(pw, headless: bool):
    """Prefer the browsers Windows already has, so nothing extra is downloaded."""
    errors = []
    for channel in ("msedge", "chrome", None):
        try:
            kw = {"channel": channel} if channel else {}
            return pw.chromium.launch(headless=headless, **kw)
        except Exception as e:  # browser not installed
            errors.append(f"{channel or 'chromium'}: {str(e).splitlines()[0]}")
    raise RuntimeError("No browser found for the FACEIT screenshot (tried Edge, Chrome, Playwright's "
                       "Chromium). Install Edge/Chrome, or run: python -m playwright install chromium\n  "
                       + "\n  ".join(errors))


def screenshot_room(mid: str, out: Path, size: tuple[int, int] = (1920, 1080),
                    timeout: float = 45.0, headless: bool = True, url: str | None = None,
                    zoom: float = 1.2) -> Path:
    """Save a screenshot of the match room to ``out``; raises on failure.

    The page is laid out at ``size / zoom`` and rendered at ``zoom``x, so the
    image is ``size`` pixels with slightly larger, sharp text.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError("Playwright is not installed: python -m pip install playwright") from e

    url = url or room_url(mid)
    view = {"width": round(size[0] / zoom), "height": round(size[1] / zoom)}
    with sync_playwright() as pw:
        browser = _launch(pw, headless)
        try:
            # Headless browsers announce themselves in the user agent; use the normal one.
            probe = browser.new_page()
            ua = probe.evaluate("navigator.userAgent").replace("HeadlessChrome", "Chrome")
            probe.close()
            ctx = browser.new_context(viewport=view, device_scale_factor=zoom, user_agent=ua,
                                      locale="en-US", color_scheme="dark")
            ctx.add_init_script(_INIT_JS)
            page = ctx.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
            try:
                page.wait_for_function(_READY_JS, timeout=timeout * 1000)
            except Exception as e:
                # keep what the browser saw, to find out why
                failed = out.with_name(out.stem + "_failed.png")
                text = ""
                try:
                    page.evaluate(_HIDE_JS, CONSENT_SELECTORS)
                    page.screenshot(path=str(failed))
                    text = " ".join(page.evaluate("document.body ? document.body.innerText : ''").split())[:160]
                except Exception:
                    pass
                raise RuntimeError(f"the match room did not load; what the browser saw: {failed} "
                                   f"(page title '{page.title()}', text '{text}')") from e
            try:  # let pictures and avatars finish
                page.wait_for_load_state("networkidle", timeout=10_000)
            except Exception:
                pass
            time.sleep(1.5)
            page.evaluate(_HIDE_JS, CONSENT_SELECTORS)
            out.parent.mkdir(parents=True, exist_ok=True)
            try:  # the stats tables load a moment after the header
                page.wait_for_function(_TABLES_JS, timeout=15_000)
                time.sleep(1.0)  # avatars
                page.locator("[data-povforge-shot]").screenshot(path=str(out))
            except Exception:  # no tables (e.g. match without stats): the top of the page
                page.evaluate("window.scrollTo(0, 0)")
                page.screenshot(path=str(out))
        finally:
            browser.close()
    return out
