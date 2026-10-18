"""On-screen overlays rendered from demo data: minimap, keyboard, player HUD."""

from __future__ import annotations

import sys
from functools import lru_cache

from PIL import ImageDraw, ImageFont

if sys.platform == "win32":
    _BOLD = ["C:/Windows/Fonts/bahnschrift.ttf", "C:/Windows/Fonts/segoeuib.ttf",
             "C:/Windows/Fonts/arialbd.ttf"]
    _CJK = ["C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf"]
else:
    _BOLD = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
    _CJK = ["/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
            "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
            "/System/Library/Fonts/PingFang.ttc"]


@lru_cache(maxsize=None)
def font(size: int, cjk: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Bold UI font; ``cjk=True`` for text that may contain Chinese etc. (player names)."""
    for path in (_CJK + _BOLD) if cjk else _BOLD:
        try:
            return ImageFont.truetype(path, max(6, int(size)))
        except OSError:
            continue
    return ImageFont.load_default(size=max(6, int(size)))


def shadow_text(d: ImageDraw.ImageDraw, xy, text: str, f, fill, anchor: str = "la",
                shadow=(0, 0, 0, 160), offset: int = 2) -> None:
    x, y = xy
    d.text((x + offset, y + offset), text, font=f, fill=shadow, anchor=anchor)
    d.text((x, y), text, font=f, fill=fill, anchor=anchor)
