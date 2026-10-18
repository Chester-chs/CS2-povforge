"""Download the external programs povforge needs (HLAE, FFmpeg) on first use.

Both are fetched from their official GitHub releases into a povforge folder
under %LOCALAPPDATA% (nothing is installed system-wide, nothing is bundled
with povforge):

- HLAE: https://github.com/advancedfx/advancedfx/releases (MIT)
- FFmpeg: https://github.com/BtbN/FFmpeg-Builds/releases (GPL build)
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

HLAE_API = "https://api.github.com/repos/advancedfx/advancedfx/releases/latest"
HLAE_LATEST = "https://github.com/advancedfx/advancedfx/releases/latest"
HLAE_KNOWN_TAG = "v2.192.8"  # last resort if the release lookup is blocked
FFMPEG_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

Progress = Callable[[str, float], None]  # (message, fraction 0..1, or -1 if unknown)


def tools_dir() -> Path:
    base = os.environ.get("POVFORGE_STATE") or os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "povforge" / "tools"


def hlae_exe() -> Path:
    return tools_dir() / "hlae" / "HLAE.exe"


def ffmpeg_exe() -> Path:
    return tools_dir() / "ffmpeg" / "bin" / "ffmpeg.exe"


def find_ffmpeg(configured: str = "ffmpeg") -> str | None:
    """The configured ffmpeg if it can be found, else the downloaded one."""
    if configured and configured != "ffmpeg" and Path(configured).is_file():
        return configured
    on_path = shutil.which(configured or "ffmpeg")
    if on_path:
        return on_path
    if ffmpeg_exe().is_file():
        return str(ffmpeg_exe())
    return None


def _get(url: str, accept: str | None = None):
    req = urllib.request.Request(url, headers={"User-Agent": "cs2-povforge"})
    if accept:
        req.add_header("Accept", accept)
    return urllib.request.urlopen(req, timeout=60)


def _download(url: str, dest: Path, what: str, progress: Progress | None) -> None:
    with _get(url) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if progress:
                progress(f"Downloading {what} ({done >> 20} MB)", done / total if total else -1)


def _extract(zip_path: Path, target: Path, strip_top: bool) -> None:
    """Unzip into ``target`` (replacing it); ``strip_top`` drops a single top folder."""
    tmp = Path(tempfile.mkdtemp(dir=target.parent))
    try:
        with zipfile.ZipFile(zip_path) as z:
            for m in z.infolist():  # refuse paths that would escape the folder
                p = (tmp / m.filename).resolve()
                if not str(p).startswith(str(tmp.resolve())):
                    raise RuntimeError(f"Unsafe path in {zip_path.name}: {m.filename}")
            z.extractall(tmp)
        src = tmp
        entries = list(tmp.iterdir())
        if strip_top and len(entries) == 1 and entries[0].is_dir():
            src = entries[0]
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(src), str(target))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _hlae_url_for(tag: str) -> str:
    # tag "v2.192.8" -> asset "hlae_2_192_8.zip"
    return (f"https://github.com/advancedfx/advancedfx/releases/download/{tag}/"
            f"hlae_{tag.lstrip('v').replace('.', '_')}.zip")


def latest_hlae() -> tuple[str, str]:
    """(tag, zip url) of the newest HLAE release."""
    try:
        with _get(HLAE_API, "application/vnd.github+json") as r:
            release = json.load(r)
        for a in release.get("assets", []):
            n = a["name"].lower()
            if n.startswith("hlae_") and n.endswith(".zip"):
                return release.get("tag_name", ""), a["browser_download_url"]
    except Exception:
        pass
    try:  # the web page redirects to .../releases/tag/<tag>
        with _get(HLAE_LATEST) as r:
            tag = r.geturl().rstrip("/").rsplit("/", 1)[-1]
        if tag.startswith("v") and tag[1:2].isdigit():
            return tag, _hlae_url_for(tag)
    except Exception:
        pass
    return HLAE_KNOWN_TAG, _hlae_url_for(HLAE_KNOWN_TAG)


def install_hlae(progress: Progress | None = None) -> Path:
    tools_dir().mkdir(parents=True, exist_ok=True)
    if progress:
        progress("Looking up the latest HLAE release", -1)
    tag, url = latest_hlae()
    zip_path = tools_dir() / url.rsplit("/", 1)[-1]
    _download(url, zip_path, f"HLAE {tag}", progress)
    if progress:
        progress("Unpacking HLAE", -1)
    _extract(zip_path, tools_dir() / "hlae", strip_top=False)
    zip_path.unlink(missing_ok=True)
    if not hlae_exe().is_file():
        raise RuntimeError("HLAE was downloaded but HLAE.exe is missing.")
    return hlae_exe()


def install_ffmpeg(progress: Progress | None = None) -> Path:
    tools_dir().mkdir(parents=True, exist_ok=True)
    zip_path = tools_dir() / "ffmpeg.zip"
    _download(FFMPEG_URL, zip_path, "FFmpeg", progress)
    if progress:
        progress("Unpacking FFmpeg", -1)
    _extract(zip_path, tools_dir() / "ffmpeg", strip_top=True)
    zip_path.unlink(missing_ok=True)
    for extra in ("ffplay.exe",):  # player, not needed
        (ffmpeg_exe().parent / extra).unlink(missing_ok=True)
    if not ffmpeg_exe().is_file():
        raise RuntimeError("FFmpeg was downloaded but ffmpeg.exe is missing.")
    return ffmpeg_exe()
