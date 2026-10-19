"""Drive the Edge or Chrome already on the PC through its DevTools protocol.

Used for the FACEIT match-room screenshot. Talks to the browser directly over
a local WebSocket, so no browser automation package (and no extra browser
download) is needed. Only what the screenshot needs is here.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path


def find_browser() -> Path | None:
    """Edge first (every Windows PC has it), then Chrome; Chromium elsewhere."""
    if sys.platform == "win32":
        pf86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        local = Path(os.environ.get("LOCALAPPDATA", ""))
        for p in (pf86 / "Microsoft/Edge/Application/msedge.exe", pf / "Microsoft/Edge/Application/msedge.exe",
                  pf / "Google/Chrome/Application/chrome.exe", pf86 / "Google/Chrome/Application/chrome.exe",
                  local / "Google/Chrome/Application/chrome.exe"):
            if p.is_file():
                return p
    for name in ("microsoft-edge", "google-chrome", "chromium", "chromium-browser", "chrome"):
        exe = shutil.which(name)
        if exe:
            return Path(exe)
    env = os.environ.get("POVFORGE_BROWSER")
    return Path(env) if env and Path(env).is_file() else None


# --- a minimal WebSocket client (RFC 6455), enough for DevTools on localhost -----

class WebSocket:
    def __init__(self, url: str, timeout: float = 60.0):
        assert url.startswith("ws://")
        hostport, _, path = url[5:].partition("/")
        host, _, port = hostport.partition(":")
        self.sock = socket.create_connection((host, int(port or 80)), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                           "Sec-WebSocket-Version: 13\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise ConnectionError("DevTools closed the connection")
            head += chunk
        if b" 101 " not in head.split(b"\r\n", 1)[0]:
            raise ConnectionError(f"DevTools refused the connection: {head[:80]!r}")
        self.buf = head.split(b"\r\n\r\n", 1)[1]

    def _recv_exact(self, n: int) -> bytes:
        while len(self.buf) < n:
            chunk = self.sock.recv(max(65536, n - len(self.buf)))
            if not chunk:
                raise ConnectionError("DevTools closed the connection")
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def send(self, text: str) -> None:
        data = text.encode("utf-8")
        head = bytes([0x81])
        n = len(data)
        if n < 126:
            head += bytes([0x80 | n])
        elif n < 65536:
            head += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            head += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        self.sock.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def recv(self) -> str:
        parts = []
        while True:
            b1, b2 = self._recv_exact(2)
            fin, op, n = b1 & 0x80, b1 & 0x0F, b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._recv_exact(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._recv_exact(8))[0]
            mask = self._recv_exact(4) if b2 & 0x80 else None
            payload = self._recv_exact(n)
            if mask:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if op == 0x8:
                raise ConnectionError("DevTools closed the connection")
            if op == 0x9:                       # ping
                continue
            if op in (0x1, 0x2, 0x0):
                parts.append(payload)
                if fin:
                    return b"".join(parts).decode("utf-8", errors="replace")

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


# --- the browser ---------------------------------------------------------------------

class Browser:
    """A private, temporary browser session (its own profile, deleted afterwards)."""

    def __init__(self, headless: bool = True, size: tuple[int, int] = (1600, 900), timeout: float = 30.0):
        exe = find_browser()
        if exe is None:
            raise RuntimeError("No Edge or Chrome found for the FACEIT screenshot.")
        self.profile = Path(tempfile.mkdtemp(prefix="povforge-browser-"))
        args = [str(exe), "--remote-debugging-port=0", f"--user-data-dir={self.profile}", "--no-first-run",
                "--no-default-browser-check", "--disable-extensions", "--mute-audio", "--hide-scrollbars",
                f"--window-size={size[0]},{size[1]}", "about:blank"]
        if headless:
            args.insert(1, "--headless=new")
        if sys.platform.startswith("linux") and os.geteuid() == 0:
            args.insert(1, "--no-sandbox")
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        self.proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        port_file = self.profile / "DevToolsActivePort"
        end = time.time() + timeout
        while not port_file.exists() or len(port_file.read_text().splitlines()) < 2:
            if time.time() > end or self.proc.poll() is not None:
                self.close()
                raise RuntimeError("The browser for the FACEIT screenshot did not start.")
            time.sleep(0.1)
        self.port = int(port_file.read_text().splitlines()[0])

    def page(self) -> "Page":
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/list", timeout=10) as r:
            targets = json.load(r)
        page = next((t for t in targets if t.get("type") == "page"), None)
        if page is None:
            req = urllib.request.Request(f"http://127.0.0.1:{self.port}/json/new?about:blank", method="PUT")
            with urllib.request.urlopen(req, timeout=10) as r:
                page = json.load(r)
        return Page(WebSocket(page["webSocketDebuggerUrl"]))

    def close(self) -> None:
        try:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
        except Exception:
            pass
        for _ in range(10):                      # the profile is in use until the browser has gone
            shutil.rmtree(self.profile, ignore_errors=True)
            if not self.profile.exists():
                break
            time.sleep(0.3)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


class Page:
    def __init__(self, ws: WebSocket):
        self.ws, self.next_id = ws, 0

    def call(self, method: str, **params):
        self.next_id += 1
        mid = self.next_id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error'].get('message')}")
                return msg.get("result", {})

    def evaluate(self, expression: str, await_promise: bool = False):
        r = self.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=await_promise)
        if r.get("exceptionDetails"):
            raise RuntimeError(r["exceptionDetails"].get("text", "script error"))
        return r.get("result", {}).get("value")

    def wait_for(self, expression: str, timeout: float) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            try:
                if self.evaluate(expression):
                    return True
            except RuntimeError:
                pass
            time.sleep(0.4)
        return False

    def screenshot(self, out: Path, clip: dict | None = None) -> Path:
        params = {"format": "png"}
        if clip:
            params.update(clip=dict(clip, scale=1), captureBeyondViewport=True)
        data = self.call("Page.captureScreenshot", **params)["data"]
        out.write_bytes(base64.b64decode(data))
        return out

    def close(self) -> None:
        self.ws.close()
