"""Incremental updates: only changed files are downloaded (over HTTP range
requests, through a redirect like GitHub's), then swapped in by the PowerShell
step, which puts everything back if something fails."""

import json
import os
import shutil
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from povforge import selfupdate as su

POWERSHELL = shutil.which(os.environ.get("POVFORGE_POWERSHELL", "powershell.exe")) or shutil.which("pwsh")


def write(root: Path, files: dict) -> Path:
    for rel, data in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return root


@pytest.fixture
def release(tmp_path):
    """v1 installed; v2 published as PovForge-windows.zip behind a redirect."""
    big = os.urandom(3 << 20)
    old = write(tmp_path / "app", {"PovForge.exe": b"exe v1", "_internal/lib.dll": b"lib v1", "ffmpeg/ffmpeg.exe": big,
                                   "_internal/gone.txt": b"old only", "unins000.exe": b"uninstaller"})
    new = write(tmp_path / "v2", {"PovForge.exe": b"exe v2", "_internal/lib.dll": b"lib v1", "ffmpeg/ffmpeg.exe": big,
                                  "_internal/new.txt": b"new in v2"})
    (new / "manifest.json").write_text(json.dumps(su.make_manifest(new, "2.0")))
    (old / "manifest.json").write_text(json.dumps(su.make_manifest(old, "1.0")))
    z = tmp_path / "PovForge-windows.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as f:
        for p in sorted(new.rglob("*")):
            if p.is_file():
                f.write(p, "PovForge/" + p.relative_to(new).as_posix())
    data, hits = z.read_bytes(), []

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path == "/download/PovForge-windows.zip":          # like github.com -> file server
                self.send_response(302)
                self.send_header("Location", "/files/zip")
                self.end_headers()
                return
            a, b = self.headers["Range"].split("=")[1].split("-")
            a, b = int(a), min(int(b), len(data) - 1)
            hits.append(b - a + 1)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {a}-{b}/{len(data)}")
            self.send_header("Content-Length", str(b - a + 1))
            self.end_headers()
            self.wfile.write(data[a:b + 1])
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield old, new, f"http://127.0.0.1:{srv.server_address[1]}/download/PovForge-windows.zip", hits
    srv.shutdown()


def test_only_changed_files_are_downloaded(release, tmp_path):
    old, new, url, hits = release
    plan = su.prepare(old, url, "1.0", tmp_path / "work")
    assert sorted(plan["changed"]) == ["PovForge.exe", "_internal/new.txt"]
    assert plan["removed"] == ["_internal/gone.txt"]                  # the uninstaller is kept
    assert sum(hits) < 300_000                                       # the 3 MB file was not fetched
    assert (tmp_path / "work/stage/PovForge.exe").read_bytes() == b"exe v2"


@pytest.mark.skipif(POWERSHELL is None, reason="needs PowerShell")
def test_apply_swaps_files_in(release, tmp_path, monkeypatch):
    monkeypatch.setenv("POVFORGE_POWERSHELL", POWERSHELL)
    old, new, url, _ = release
    work = tmp_path / "work"
    plan = su.prepare(old, url, "1.0", work)
    assert su.apply(old, work, plan, tmp_path / "update.log", relaunch=False, wait=True) == 0
    assert su.make_manifest(old, "2.0")["files"] == json.loads((new / "manifest.json").read_text())["files"]
    assert (old / "unins000.exe").exists() and not (old / "_internal/gone.txt").exists()
    assert json.loads((old / "manifest.json").read_text())["version"] == "2.0"
    assert not work.exists()                                          # cleaned up
    assert "updated to 2.0" in (tmp_path / "update.log").read_text(encoding="utf-8")


@pytest.mark.skipif(POWERSHELL is None, reason="needs PowerShell")
def test_a_failed_swap_puts_the_old_files_back(release, tmp_path, monkeypatch):
    monkeypatch.setenv("POVFORGE_POWERSHELL", POWERSHELL)
    old, new, url, _ = release
    before = su.make_manifest(old, "1.0")
    work = tmp_path / "work"
    plan = su.prepare(old, url, "1.0", work)
    (work / "stage/_internal/new.txt").unlink()                       # the second copy will fail
    assert su.apply(old, work, plan, tmp_path / "update.log", relaunch=False, wait=True) == 1
    assert su.make_manifest(old, "1.0")["files"] == before["files"]   # exactly as before
    assert "putting the old files back" in (tmp_path / "update.log").read_text(encoding="utf-8")
