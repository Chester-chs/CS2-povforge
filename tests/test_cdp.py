"""The FACEIT screenshot path against a local page shaped like the match room,
with whatever Edge/Chrome is installed (skipped when there is none)."""

import json
import shutil
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from povforge import cdp, faceit

MID = "1-a34d80c7-3b13-4d61-a987-5f907440193a"


@pytest.fixture
def room(tmp_path):
    site = tmp_path / "site"
    (site / "api/match/v2/match").mkdir(parents=True)
    shutil.copy(Path(__file__).with_name("fake_faceit_room.html"), site / "index.html")
    (site / "api/match/v2/match" / MID).write_text(json.dumps({"payload": {"startedAt": "2026-10-18T20:13:00Z"}}))

    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(site)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/index.html"
    srv.shutdown()


@pytest.mark.skipif(cdp.find_browser() is None, reason="no Edge/Chrome here")
def test_room_screenshot_through_devtools(room, tmp_path):
    from PIL import Image
    out, info = tmp_path / "room.png", tmp_path / "match.json"
    faceit.screenshot_room(MID, out, (1920, 1080), url=room, info_out=info, timeout=30)
    w, h = Image.open(out).size
    assert w == 1920 and 100 < h < 1080                 # the scoreboard only, at 1.2x
    assert json.loads(info.read_text())["startedAt"] == "2026-10-18T20:13:00Z"
