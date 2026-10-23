"""Radar images and coordinate transforms for the minimap.

The radar PNGs and overview files are Valve's own game assets. We don't ship
them in this repository; they are downloaded on first use from
https://github.com/MurkyYT/cs2-map-icons, which extracts them automatically
from every CS2 update, and cached locally.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path

SOURCE_BASE = "https://raw.githubusercontent.com/MurkyYT/cs2-map-icons/main"
RADAR_SIZE = 1024  # all CS2 radar images are 1024x1024


def cache_dir() -> Path:
    if os.environ.get("POVFORGE_CACHE"):
        base = Path(os.environ["POVFORGE_CACHE"])
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "povforge"
    else:
        base = Path.home() / ".cache" / "povforge"
    d = base / "maps"
    d.mkdir(parents=True, exist_ok=True)
    return d


# --- Valve KeyValues (overview .txt) ------------------------------------------

_TOKEN = re.compile(r'"([^"]*)"|([{}])|//[^\n]*|(\S+)')


def parse_keyvalues(text: str) -> dict:
    tokens = []
    for m in _TOKEN.finditer(text):
        if m.group(1) is not None:
            tokens.append(("s", m.group(1)))
        elif m.group(2):
            tokens.append((m.group(2), m.group(2)))
        elif m.group(3):
            tokens.append(("s", m.group(3)))

    pos = 0

    def block() -> dict:
        nonlocal pos
        out: dict = {}
        while pos < len(tokens):
            kind, val = tokens[pos]
            if kind == "}":
                pos += 1
                return out
            pos += 1
            if pos >= len(tokens):
                break
            nkind, nval = tokens[pos]
            if nkind == "{":
                pos += 1
                out[val] = block()
            else:
                pos += 1
                out[val] = nval
        return out

    return block()


@dataclass(frozen=True)
class MapInfo:
    name: str
    pos_x: float
    pos_y: float
    scale: float
    lower_below_z: float | None = None   # z below this uses the lower radar

    def to_radar(self, x: float, y: float) -> tuple[float, float]:
        """World coordinates -> pixel on the 1024x1024 radar image."""
        return (x - self.pos_x) / self.scale, (self.pos_y - y) / self.scale

    def is_lower(self, z: float) -> bool:
        return self.lower_below_z is not None and z < self.lower_below_z


def map_info_from_text(name: str, text: str) -> MapInfo:
    kv = parse_keyvalues(text)
    root = next(iter(kv.values())) if kv else {}
    lower = None
    sections = root.get("verticalsections")
    if isinstance(sections, dict) and isinstance(sections.get("lower"), dict):
        lower = float(sections["lower"]["AltitudeMax"])
    return MapInfo(
        name=name,
        pos_x=float(root["pos_x"]),
        pos_y=float(root["pos_y"]),
        scale=float(root["scale"]),
        lower_below_z=lower,
    )


# --- download & cache ---------------------------------------------------------

def get_map_thumbnail(name: str) -> Path:
    """Return the game's scenery thumbnail, independently of radar assets."""
    if not re.fullmatch(r"[a-z0-9_]{1,80}", name):
        raise ValueError("Invalid map name")
    dest = cache_dir() / f"{name}_scene.png"
    if dest.is_file():
        return dest
    req = urllib.request.Request(
        f"{SOURCE_BASE}/images/thumbs/{name}_png.png",
        headers={"User-Agent": "cs2-povforge"},
    )
    limit = 8 * 1024 * 1024
    with urllib.request.urlopen(req, timeout=8) as response:
        data = response.read(limit + 1)
    if len(data) > limit or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Invalid map thumbnail")
    # Unique temporary files keep simultaneous requests from corrupting the cache.
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=dest.parent, suffix=".part", delete=False) as f:
            tmp = Path(f.name)
            f.write(data)
        tmp.replace(dest)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return dest

def _download(url: str, dest: Path) -> None:
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": "cs2-povforge"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        f.write(r.read())
    tmp.replace(dest)


@dataclass
class MapAssets:
    info: MapInfo
    radar: Path
    radar_lower: Path | None


def get_map(name: str, refresh: bool = False) -> MapAssets:
    """Return radar assets for ``name`` (e.g. "de_dust2"), downloading if needed."""
    d = cache_dir()
    txt = d / f"{name}.txt"
    png = d / f"{name}_radar_psd.png"
    files = [(f"data/radar_info/{name}.txt", txt), (f"images/radars/{name}_radar_psd.png", png)]
    for remote, local in files:
        if refresh or not local.exists():
            try:
                _download(f"{SOURCE_BASE}/{remote}", local)
            except Exception as e:
                raise RuntimeError(
                    f"Could not get radar data for map '{name}' ({e}). "
                    "Workshop and unofficial maps have no radar; use --no-minimap."
                ) from e
    info = map_info_from_text(name, txt.read_text(encoding="utf-8", errors="replace"))
    lower = None
    if info.lower_below_z is not None:
        lower = d / f"{name}_lower_radar_psd.png"
        if refresh or not lower.exists():
            try:
                _download(f"{SOURCE_BASE}/images/radars/{name}_lower_radar_psd.png", lower)
            except Exception:
                lower = None
    return MapAssets(info, png, lower)
