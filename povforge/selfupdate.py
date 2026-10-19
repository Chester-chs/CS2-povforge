"""Update the installed app by downloading only the files that changed.

Every build ships ``manifest.json`` (each file's size and SHA-256). A release's
``PovForge-windows.zip`` holds the whole app plus that manifest. Updating:

1. read the new manifest from inside the zip on GitHub, fetching only the bytes
   needed (HTTP range requests);
2. compare it with this install's files and download just the ones that differ,
   checking each against its SHA-256;
3. after the app has closed, a small hidden PowerShell step moves the old files
   aside, puts the new ones in place (putting everything back if anything fails),
   records the new version for Windows' Apps list, and opens PovForge again.

Anything going wrong before step 3 leaves the install untouched; the app then
falls back to the full installer.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

MANIFEST = "manifest.json"
KEEP = {"unins000.exe", "unins000.dat", MANIFEST}          # the installer's files and the manifest itself
ZIP_ROOT = "PovForge/"
UNINSTALL_KEY = r"HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{6E0B5A4C-2F1E-4C7B-9C64-6A1D2C9F7B11}_is1"

Progress = Callable[[int, int], None]                       # (bytes done, bytes to fetch)


# --- manifests -----------------------------------------------------------------------

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def make_manifest(app_dir: Path, version: str) -> dict:
    files = {}
    for p in sorted(app_dir.rglob("*")):
        if p.is_file():
            rel = p.relative_to(app_dir).as_posix()
            if rel.lower() not in KEEP:
                files[rel] = {"size": p.stat().st_size, "sha256": file_hash(p)}
    return {"version": version, "files": files}


def local_manifest(app_dir: Path, version: str) -> dict:
    """This install's files: the shipped manifest when it matches, else measured."""
    f = app_dir / MANIFEST
    if f.exists():
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
            if m.get("version") == version:
                return m
        except Exception:
            pass
    return make_manifest(app_dir, version)


def changes(new: dict, old: dict) -> tuple[list[str], list[str]]:
    """(files to fetch, files to remove) to turn ``old`` into ``new``."""
    nf, of = new["files"], old["files"]
    fetch = [p for p, i in nf.items() if of.get(p, {}).get("sha256") != i["sha256"]]
    remove = [p for p in of if p not in nf and p.lower() not in KEEP]
    return fetch, remove


# --- reading a zip on a web server, a few bytes at a time ----------------------------

class HttpRangeFile(io.RawIOBase):
    """A read-only, seekable file over HTTP range requests (zipfile needs only seek/read)."""

    BLOCK = 256 * 1024

    def __init__(self, url: str):
        self.origin, self.pos = url, 0
        self._resolve()
        self.cache_start, self.cache = -1, b""

    def _resolve(self) -> None:
        req = urllib.request.Request(self.origin, headers={"Range": "bytes=0-0", "User-Agent": "PovForge"})
        with urllib.request.urlopen(req, timeout=30) as r:
            if r.status != 206 or not r.headers.get("Content-Range"):
                raise RuntimeError("The download server doesn't allow partial downloads.")
            self.url = r.geturl()                     # GitHub redirects to its file server
            self.size = int(r.headers["Content-Range"].rsplit("/", 1)[1])

    def _fetch(self, start: int, end: int) -> bytes:
        for attempt in range(3):
            try:
                req = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{end}", "User-Agent": "PovForge"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    if r.status != 206:
                        raise RuntimeError("The download server ignored a partial download request.")
                    return r.read()
            except urllib.error.HTTPError as e:
                if e.code in (401, 403, 404, 410) and attempt < 2:
                    self._resolve()                   # the signed file-server link expired
                    continue
                raise
        raise RuntimeError("Downloading failed.")

    def prefetch(self, start: int, end: int, on_bytes: Callable[[int], None] | None = None) -> None:
        """Load bytes start..end (inclusive) in one streamed request, so reading a
        big file from the zip doesn't take hundreds of small requests."""
        end = min(end, self.size - 1)
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{end}", "User-Agent": "PovForge"})
        try:
            r = urllib.request.urlopen(req, timeout=60)
        except urllib.error.HTTPError as e:
            if e.code not in (401, 403, 404, 410):
                raise
            self._resolve()
            req = urllib.request.Request(self.url, headers={"Range": f"bytes={start}-{end}", "User-Agent": "PovForge"})
            r = urllib.request.urlopen(req, timeout=60)
        with r:
            if r.status != 206:
                raise RuntimeError("The download server ignored a partial download request.")
            parts = []
            while chunk := r.read(1 << 20):
                parts.append(chunk)
                if on_bytes:
                    on_bytes(len(chunk))
        self.cache_start, self.cache = start, b"".join(parts)

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        self.pos = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        return self.pos

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        out = bytearray()
        while n > 0:
            if not (self.cache_start <= self.pos < self.cache_start + len(self.cache)):
                end = min(self.size, self.pos + max(n, self.BLOCK)) - 1
                self.cache_start, self.cache = self.pos, self._fetch(self.pos, end)
            i = self.pos - self.cache_start
            piece = self.cache[i:i + n]
            out += piece
            self.pos += len(piece)
            n -= len(piece)
        return bytes(out)

    def readinto(self, b) -> int:
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def open_zip(source: str | Path) -> tuple[zipfile.ZipFile, HttpRangeFile | None]:
    if str(source).startswith(("http://", "https://")):
        raw = HttpRangeFile(str(source))
        return zipfile.ZipFile(raw), raw
    return zipfile.ZipFile(source), None


def _rel(info: zipfile.ZipInfo) -> str:
    return info.filename.replace("\\", "/")[len(ZIP_ROOT):]


def _end_of(info: zipfile.ZipInfo) -> int:
    """Last byte of a member's local header + data (+ room for its extra field)."""
    return info.header_offset + 30 + len(info.orig_filename.encode("utf-8")) + 1024 + info.compress_size


def _runs(infos: list[zipfile.ZipInfo], gap: int = 256 * 1024, most: int = 64 << 20) -> list[list[zipfile.ZipInfo]]:
    """Group members lying close together in the zip (fetching a small unneeded gap
    is cheaper than another request), capped so one group stays modest in memory."""
    runs: list[list[zipfile.ZipInfo]] = []
    for info in sorted(infos, key=lambda i: i.header_offset):
        if runs and info.header_offset - _end_of(runs[-1][-1]) < gap \
                and _end_of(info) - runs[-1][0].header_offset < most:
            runs[-1].append(info)
        else:
            runs.append([info])
    return runs


def _members(z: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    out = {}
    for info in z.infolist():
        name = info.filename.replace("\\", "/")
        if name.startswith(ZIP_ROOT) and not name.endswith("/"):
            out[name[len(ZIP_ROOT):]] = info
    return out


# --- the update ----------------------------------------------------------------------

def prepare(app_dir: Path, source: str | Path, version: str, work: Path,
            progress: Progress | None = None) -> dict:
    """Download what changed into ``work/stage``; returns the plan for apply()."""
    z, raw = open_zip(source)
    members = _members(z)
    if MANIFEST not in members:
        raise RuntimeError("This release has no file list; using the full installer.")
    new = json.loads(z.read(members[MANIFEST]).decode("utf-8"))
    fetch, remove = changes(new, local_manifest(app_dir, version))
    missing = [p for p in fetch if p not in members]
    if missing:
        raise RuntimeError(f"The release zip lacks {missing[0]}.")
    stage = work / "stage"
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    total = sum(members[p].compress_size for p in fetch) or 1
    done = 0
    # neighbours in the zip come down together: one request per run of files, not per file
    for group in _runs([members[p] for p in fetch]):
        if raw is not None:
            first, last = group[0], group[-1]
            seen = [0]

            def tick(n: int, base=done) -> None:
                seen[0] += n
                if progress:
                    progress(min(base + seen[0], total), total)
            raw.prefetch(first.header_offset, _end_of(last), tick)
        for info in group:
            p = _rel(info)
            dest = stage / p
            dest.parent.mkdir(parents=True, exist_ok=True)
            h = hashlib.sha256()
            with z.open(info) as src, open(dest, "wb") as out:
                while chunk := src.read(1 << 20):
                    out.write(chunk)
                    h.update(chunk)
            if h.hexdigest() != new["files"][p]["sha256"]:
                raise RuntimeError(f"{p} didn't download correctly (checksum differs).")
            done += info.compress_size
            if progress:
                progress(done, total)
    (stage / MANIFEST).write_text(json.dumps(new), encoding="utf-8")
    return {"version": new["version"], "changed": fetch, "removed": remove, "bytes": total if fetch else 0}


APPLY_PS1 = r"""
param([string]$Config)
$ErrorActionPreference = 'Stop'
$c = Get-Content -Raw -LiteralPath $Config -Encoding UTF8 | ConvertFrom-Json
function Log([string]$m) { Add-Content -LiteralPath $c.log -Value ("{0} {1}" -f (Get-Date -Format 's'), $m) -Encoding UTF8 }
function Retry([scriptblock]$b) {
  for ($i = 0; $i -lt 60; $i++) { try { & $b; return } catch { Start-Sleep -Milliseconds 250 } }
  & $b
}
Log "update to $($c.version): waiting for PovForge to close"
if ($c.wait_pid -gt 0) { try { Wait-Process -Id $c.wait_pid -Timeout 90 -ErrorAction SilentlyContinue } catch {} }
Start-Sleep -Milliseconds 700
$moved = New-Object System.Collections.Generic.List[string]
$added = New-Object System.Collections.Generic.List[string]
$ok = $true
try {
  foreach ($rel in @($c.changed)) {
    $src = Join-Path $c.stage $rel; $dst = Join-Path $c.app $rel; $bk = Join-Path $c.backup $rel
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null
    if (Test-Path -LiteralPath $dst) {
      New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bk) | Out-Null
      Retry { Move-Item -LiteralPath $dst -Destination $bk -Force }
      $moved.Add($rel)
    }
    Retry { Copy-Item -LiteralPath $src -Destination $dst -Force }
    $added.Add($rel)
  }
  foreach ($rel in @($c.removed)) {
    $dst = Join-Path $c.app $rel; $bk = Join-Path $c.backup $rel
    if (Test-Path -LiteralPath $dst) {
      New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bk) | Out-Null
      Retry { Move-Item -LiteralPath $dst -Destination $bk -Force }
      $moved.Add($rel)
    }
  }
  Copy-Item -LiteralPath (Join-Path $c.stage 'manifest.json') -Destination (Join-Path $c.app 'manifest.json') -Force
  if ($c.uninstall_key -and (Test-Path -LiteralPath $c.uninstall_key)) {
    try { Set-ItemProperty -LiteralPath $c.uninstall_key -Name DisplayVersion -Value $c.version } catch {}
  }
  Log "updated to $($c.version): $($added.Count) file(s) replaced, $(@($c.removed).Count) removed"
} catch {
  $ok = $false
  Log "failed: $($_.Exception.Message); putting the old files back"
  foreach ($rel in $added) { try { Remove-Item -LiteralPath (Join-Path $c.app $rel) -Force } catch {} }
  foreach ($rel in $moved) {
    try { Move-Item -LiteralPath (Join-Path $c.backup $rel) -Destination (Join-Path $c.app $rel) -Force }
    catch { Log "could not put back $rel" }
  }
}
if ($c.relaunch) { Start-Process -FilePath (Join-Path $c.app 'PovForge.exe') -WorkingDirectory $c.app }
if ($ok) { try { Remove-Item -LiteralPath $c.work -Recurse -Force } catch {} ; exit 0 }
exit 1
"""


def apply(app_dir: Path, work: Path, plan: dict, log: Path, wait_pid: int = 0,
          relaunch: bool = True, wait: bool = False) -> int | None:
    """Swap the staged files in (after ``wait_pid`` has exited). With ``wait``,
    runs in the foreground and returns the exit code (for tests)."""
    script = work / "apply.ps1"
    script.write_text(APPLY_PS1, encoding="utf-8-sig")       # BOM: Windows PowerShell reads it as UTF-8
    cfg = {"app": str(app_dir), "stage": str(work / "stage"), "backup": str(work / "backup"), "work": str(work),
           "changed": plan["changed"], "removed": plan["removed"], "version": plan["version"],
           "log": str(log), "wait_pid": wait_pid, "relaunch": relaunch, "uninstall_key": UNINSTALL_KEY}
    (work / "apply.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    cmd = [os.environ.get("POVFORGE_POWERSHELL", "powershell.exe"), "-NoProfile", "-NonInteractive",
           "-ExecutionPolicy", "Bypass", *(["-WindowStyle", "Hidden"] if sys.platform == "win32" else []),
           "-File", str(script), "-Config", str(work / "apply.json")]
    flags = (0x08000000 | 0x00000200) if sys.platform == "win32" else 0   # no window, own process group
    if wait:
        return subprocess.run(cmd, creationflags=flags).returncode
    subprocess.Popen(cmd, creationflags=flags, close_fds=True, cwd=str(work))
    return None


def app_dir() -> Path:
    return Path(sys.executable).resolve().parent
